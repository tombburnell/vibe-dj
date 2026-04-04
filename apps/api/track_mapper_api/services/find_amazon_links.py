"""Batch Amazon link discovery for source tracks in the Need (rejected) queue."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.source import SourceTrack
from track_mapper_api.services.amazon_music_search import (
    AmazonMusicSearcher,
    AmazonSearchResult,
)
from track_mapper_api.services.matching import resolve_snapshot_id
from track_mapper_api.services.source_link_actions import is_source_rejected_for_snapshot

logger = logging.getLogger(__name__)

MAX_IDS_PER_REQUEST = 200


def _amazon_search_delay_seconds() -> float:
    ms = int(os.environ.get("AMAZON_SEARCH_DELAY_MS", "2000"))
    return max(0.0, ms / 1000.0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _best_link_display_title(r: AmazonSearchResult) -> str | None:
    """Single-line label for the top search result."""
    pt = (r.page_title or "").strip()
    if pt:
        return pt
    t = (r.title or "").strip()
    a = (r.artist or "").strip()
    if t and a:
        return f"{t} — {a}"
    if t:
        return t
    if a:
        return a
    return None


def _results_to_candidate_dicts(
    results: list[AmazonSearchResult],
) -> tuple[str | None, str | None, list[dict], str | None, float | None]:
    """Best URL, price, alternates, display title, match score (0–100 scale from searcher)."""
    with_url = [r for r in results if r.url]
    if not with_url:
        return None, None, [], None, None
    best = with_url[0]
    best_url = best.url
    best_price = best.price
    best_title = _best_link_display_title(best)
    best_score = float(best.match_score)
    alts: list[dict] = []
    for r in with_url[1:]:
        alts.append(
            {
                "url": r.url,
                "title": r.title,
                "artist": r.artist,
                "match_score": r.match_score,
                "price": r.price,
            }
        )
    return best_url, best_price, alts, best_title, best_score


@dataclass
class FindAmazonLinksStats:
    searched_count: int = 0
    skipped_not_need_count: int = 0
    skipped_cached_count: int = 0
    error_count: int = 0


async def find_amazon_links_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_ids: list[uuid.UUID] | None,
    force: bool,
) -> FindAmazonLinksStats:
    stats = FindAmazonLinksStats()
    snap = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=None)
    if snap is None:
        logger.info("find_amazon_links: no library snapshot for user=%s", user_id)
        return stats

    if source_track_ids is not None:
        raw_ids = source_track_ids[:MAX_IDS_PER_REQUEST]
        if not raw_ids:
            return stats
        res = await db.execute(
            select(SourceTrack).where(
                SourceTrack.user_id == user_id,
                SourceTrack.id.in_(raw_ids),
            )
        )
        tracks = list(res.scalars().all())
    else:
        res = await db.execute(select(SourceTrack).where(SourceTrack.user_id == user_id))
        tracks = list(res.scalars().all())

    delay = _amazon_search_delay_seconds()
    searcher = AmazonMusicSearcher()
    first_eligible_search = True

    for st in tracks:
        need = await is_source_rejected_for_snapshot(
            db,
            user_id=user_id,
            source_track_id=st.id,
            library_snapshot_id=snap,
        )
        if not need:
            stats.skipped_not_need_count += 1
            continue

        if not force and st.amazon_last_searched_at is not None:
            stats.skipped_cached_count += 1
            continue

        if not first_eligible_search and delay > 0:
            await asyncio.sleep(delay)
        first_eligible_search = False

        stub = SimpleNamespace(title=st.title, artist=st.artist)
        try:
            results = await asyncio.to_thread(searcher.search_track, stub)
        except Exception as e:
            logger.exception(
                "find_amazon_links search failed source_track_id=%s: %s",
                st.id,
                e,
            )
            stats.error_count += 1
            st.amazon_last_searched_at = _utcnow()
            st.amazon_candidates_json = []
            st.amazon_link_title = None
            st.amazon_link_match_score = None
            continue

        stats.searched_count += 1
        best_url, best_price, alts, best_title, best_score = _results_to_candidate_dicts(results)
        st.amazon_search_url = searcher.generate_amazon_link(stub)
        st.amazon_last_searched_at = _utcnow()
        st.amazon_candidates_json = alts
        if best_url:
            st.amazon_url = best_url
            st.amazon_price = best_price
            html_title = await asyncio.to_thread(searcher.fetch_link_page_title, best_url)
            if isinstance(html_title, str) and html_title.strip():
                st.amazon_link_title = html_title.strip()
            else:
                st.amazon_link_title = best_title
            st.amazon_link_match_score = best_score
        else:
            st.amazon_url = None
            st.amazon_price = None
            st.amazon_link_title = None
            st.amazon_link_match_score = None

    await db.flush()
    return stats
