"""Batch-fetch Spotify preview URLs for source tracks missing them."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import partial

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.source import SourceTrack
from track_mapper_api.services.spotify_oauth_service import get_spotify_user_access_token
from track_mapper_api.services.spotify_web_api import (
    SpotifyWebApiError,
    fetch_tracks_previews_with_fallback,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpotifyPreviewBackfillResult:
    batches_run: int
    tracks_examined: int
    previews_set: int
    marked_no_preview: int
    skipped_missing_track: int


async def backfill_missing_spotify_previews(
    db: AsyncSession,
    *,
    user_id: str,
    market: str,
    max_batches: int = 20,
    batch_delay_seconds: float = 5.0,
) -> SpotifyPreviewBackfillResult:
    """Load up to ``max_batches`` × 50 Spotify-backed rows still needing preview resolution.

    Uses a **connected Spotify user token without a forced market** when available, then
    falls back to app credentials + ``market`` (see ``fetch_tracks_previews_with_fallback``).
    """
    if max_batches < 1:
        raise ValueError("max_batches must be at least 1")
    batches_run = 0
    examined = 0
    previews_set = 0
    marked_no = 0
    skipped_missing = 0
    delay = max(0.0, batch_delay_seconds)

    while batches_run < max_batches:
        res = await db.execute(
            select(SourceTrack)
            .where(
                SourceTrack.user_id == user_id,
                SourceTrack.spotify_id.is_not(None),
                SourceTrack.spotify_preview_url.is_(None),
                SourceTrack.no_spotify_preview.is_(False),
            )
            .order_by(SourceTrack.updated_at.asc(), SourceTrack.id.asc())
            .limit(50)
        )
        batch = list(res.scalars().all())
        if not batch:
            break

        ids = [st.spotify_id for st in batch if st.spotify_id]
        if not ids:
            break

        access = await get_spotify_user_access_token(db, user_id=user_id)
        try:
            triples = await asyncio.to_thread(
                partial(
                    fetch_tracks_previews_with_fallback,
                    track_ids=ids,
                    default_market=market,
                    user_access_token=access,
                ),
            )
        except SpotifyWebApiError:
            logger.exception(
                "spotify preview backfill batch failed user_id=%s batch_size=%s",
                user_id,
                len(ids),
            )
            raise

        id_to_row = {st.spotify_id: st for st in batch if st.spotify_id}
        for spotify_id, preview_url, track_present in triples:
            st = id_to_row.get(spotify_id)
            if st is None:
                continue
            examined += 1
            if not track_present:
                skipped_missing += 1
                continue
            if preview_url:
                st.spotify_preview_url = preview_url
                st.no_spotify_preview = False
                previews_set += 1
            else:
                st.spotify_preview_url = None
                st.no_spotify_preview = True
                marked_no += 1

        await db.flush()
        batches_run += 1

        if batches_run >= max_batches or len(batch) < 50:
            break
        if delay > 0:
            await asyncio.sleep(delay)

    return SpotifyPreviewBackfillResult(
        batches_run=batches_run,
        tracks_examined=examined,
        previews_set=previews_set,
        marked_no_preview=marked_no,
        skipped_missing_track=skipped_missing,
    )
