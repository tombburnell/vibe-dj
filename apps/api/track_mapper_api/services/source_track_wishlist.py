"""Batch update source_tracks.on_wishlist (ignore / restore in UI)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.source import SourceTrack


async def set_wishlist_batch(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_ids: list[uuid.UUID],
    on_wishlist: bool,
) -> int:
    if not source_track_ids:
        raise HTTPException(status_code=400, detail="source_track_ids must not be empty")
    unique = list(dict.fromkeys(source_track_ids))
    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id.in_(unique),
        )
    )
    rows = list(res.scalars().all())
    if len(rows) != len(unique):
        raise HTTPException(status_code=404, detail="One or more source tracks not found")
    for st in rows:
        st.on_wishlist = on_wishlist
    return len(rows)
