"""Batch link discovery for source tracks in the Need (rejected) queue.

Uses :class:`MultiSiteWebSearcher` (Tidal / Amazon / SoundCloud via Serper or ``ddgs``). Results are stored in
existing ``amazon_*`` columns for API/UI compatibility.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.config import MAX_WEB_RESULTS
from track_mapper_api.models.source import SourceTrack
from track_mapper_api.services.matching import resolve_snapshot_id
from track_mapper_api.services.source_link_actions import is_source_rejected_for_snapshot
from track_mapper_api.services.web_search_service import (
    MultiSiteWebSearcher,
    WebSearchHit,
    WebSearchProvider,
    multisite_repeat_search_url,
)

logger = logging.getLogger(__name__)

MAX_IDS_PER_REQUEST = 200


def _amazon_search_delay_seconds() -> float:
    ms = int(os.environ.get("AMAZON_SEARCH_DELAY_MS", "2000"))
    return max(0.0, ms / 1000.0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hit_to_candidate_dict(h: WebSearchHit) -> dict:
    """One JSON row for `amazon_candidates_json` (includes ``broken`` for user overrides)."""
    return {
        "url": h.url,
        "title": h.title or None,
        # Do not set ``artist`` to ``matched_domain``; UI joins title + artist with " — "
        # and would show e.g. "… — soundcloud.com".
        "artist": None,
        "match_score": float(h.match_score),
        "price": None,
        "broken": False,
    }


def _hits_to_candidate_dicts(
    hits: list[WebSearchHit],
) -> tuple[str | None, str | None, list[dict], str | None, float | None]:
    """Best URL (pointer), price (none), full ordered hit list, display title, best score (0–100).

    ``amazon_candidates_json`` stores every hit (best first); ``amazon_url`` points at the
    current chosen URL (normally the first hit's URL).
    """
    if not hits:
        return None, None, [], None, None
    best = hits[0]
    best_url = best.url
    best_title = (best.title or "").strip() or None
    best_score = float(best.match_score)
    all_rows = [_hit_to_candidate_dict(h) for h in hits]
    return best_url, None, all_rows, best_title, best_score


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
    web_search_provider: WebSearchProvider | None = None,
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
    searcher = MultiSiteWebSearcher()
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

        try:
            query, hits = await asyncio.to_thread(
                searcher.search,
                artist=st.artist,
                track=st.title,
                max_results=MAX_WEB_RESULTS,
                web_search_provider=web_search_provider,
            )
        except Exception as e:
            logger.exception(
                "find_amazon_links web search failed source_track_id=%s: %s",
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
        best_url, _price, candidates_json, best_title, best_score = _hits_to_candidate_dicts(hits)
        st.amazon_search_url = multisite_repeat_search_url(
            query, web_search_provider=web_search_provider
        )
        st.amazon_last_searched_at = _utcnow()
        st.amazon_candidates_json = candidates_json
        if best_url:
            st.amazon_url = best_url
            st.amazon_price = None
            st.amazon_link_title = best_title
            st.amazon_link_match_score = best_score
        else:
            st.amazon_url = None
            st.amazon_price = None
            st.amazon_link_title = None
            st.amazon_link_match_score = None

    await db.flush()
    logger.info(
        "find_amazon_links user=%s searched=%s skipped_not_need=%s skipped_cached=%s errors=%s",
        user_id,
        stats.searched_count,
        stats.skipped_not_need_count,
        stats.skipped_cached_count,
        stats.error_count,
    )
    return stats
