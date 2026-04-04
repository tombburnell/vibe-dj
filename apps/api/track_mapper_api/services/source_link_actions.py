"""User pick / reject on source_library_links for the latest library snapshot."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.library import LibrarySnapshot, LibraryTrack
from track_mapper_api.models.link import SourceLibraryLink
from track_mapper_api.models.source import SourceTrack


async def _latest_snapshot_id(
    db: AsyncSession,
    *,
    user_id: str,
) -> uuid.UUID | None:
    res = await db.execute(
        select(LibrarySnapshot.id)
        .where(LibrarySnapshot.user_id == user_id)
        .order_by(LibrarySnapshot.imported_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def delete_all_links_for_source_snapshot(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
) -> None:
    await db.execute(
        delete(SourceLibraryLink).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == library_snapshot_id,
        )
    )


async def is_source_rejected_for_snapshot(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
) -> bool:
    """True if any reject row's rejected_through snapshot is still at or after this snapshot in library time (top_level_spec §7)."""
    curr_at = (
        await db.execute(
            select(LibrarySnapshot.imported_at).where(
                LibrarySnapshot.user_id == user_id,
                LibrarySnapshot.id == library_snapshot_id,
            )
        )
    ).scalar_one_or_none()
    if curr_at is None:
        return False
    res = await db.execute(
        select(SourceLibraryLink.id)
        .join(
            LibrarySnapshot,
            LibrarySnapshot.id == SourceLibraryLink.rejected_through_snapshot_id,
        )
        .where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.decision == "rejected",
            SourceLibraryLink.rejected_through_snapshot_id.isnot(None),
            LibrarySnapshot.imported_at >= curr_at,
        )
        .limit(1)
    )
    return res.first() is not None


async def link_mode_for_source_snapshot(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
) -> tuple[str, SourceLibraryLink | None]:
    """rejected | picked | fuzzy — reject scope can span prior snapshots; pick is for this snapshot only."""
    if await is_source_rejected_for_snapshot(
        db,
        user_id=user_id,
        source_track_id=source_track_id,
        library_snapshot_id=library_snapshot_id,
    ):
        return "rejected", None

    res = await db.execute(
        select(SourceLibraryLink).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == library_snapshot_id,
        )
    )
    links = list(res.scalars().all())
    for link in links:
        if link.decision in ("picked", "confirmed") and link.library_track_id is not None:
            return "picked", link
    return "fuzzy", None


async def pick_source_library_track(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_track_id: uuid.UUID,
    confidence: float | None,
) -> None:
    snap = await _latest_snapshot_id(db, user_id=user_id)
    if snap is None:
        raise HTTPException(status_code=400, detail="No library snapshot to match against")

    st = (
        await db.execute(
            select(SourceTrack).where(
                SourceTrack.id == source_track_id,
                SourceTrack.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if st is None:
        raise HTTPException(status_code=404, detail="Source track not found")

    lt = (
        await db.execute(
            select(LibraryTrack).where(
                LibraryTrack.id == library_track_id,
                LibraryTrack.user_id == user_id,
                LibraryTrack.library_snapshot_id == snap,
            )
        )
    ).scalar_one_or_none()
    if lt is None:
        raise HTTPException(
            status_code=400,
            detail="Library track not found or not in the current snapshot",
        )

    await delete_all_links_for_source_snapshot(
        db,
        user_id=user_id,
        source_track_id=source_track_id,
        library_snapshot_id=snap,
    )
    now = _utcnow()
    conf = float(confidence) if confidence is not None else 1.0
    db.add(
        SourceLibraryLink(
            id=uuid.uuid4(),
            user_id=user_id,
            source_track_id=source_track_id,
            library_track_id=library_track_id,
            library_snapshot_id=snap,
            decision="picked",
            confidence=conf,
            rank=1,
            rejected_through_snapshot_id=None,
            created_at=now,
            updated_at=now,
            decided_at=now,
            decided_by=user_id,
        )
    )


async def reject_source_no_match(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
) -> None:
    snap = await _latest_snapshot_id(db, user_id=user_id)
    if snap is None:
        raise HTTPException(status_code=400, detail="No library snapshot")

    st = (
        await db.execute(
            select(SourceTrack).where(
                SourceTrack.id == source_track_id,
                SourceTrack.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if st is None:
        raise HTTPException(status_code=404, detail="Source track not found")

    await delete_all_links_for_source_snapshot(
        db,
        user_id=user_id,
        source_track_id=source_track_id,
        library_snapshot_id=snap,
    )
    now = _utcnow()
    db.add(
        SourceLibraryLink(
            id=uuid.uuid4(),
            user_id=user_id,
            source_track_id=source_track_id,
            library_track_id=None,
            library_snapshot_id=snap,
            decision="rejected",
            confidence=None,
            rank=None,
            rejected_through_snapshot_id=snap,
            created_at=now,
            updated_at=now,
            decided_at=now,
            decided_by=user_id,
        )
    )


async def undo_pick_for_source(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
) -> bool:
    snap = await _latest_snapshot_id(db, user_id=user_id)
    if snap is None:
        return False
    res = await db.execute(
        delete(SourceLibraryLink).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == snap,
            SourceLibraryLink.decision.in_(("picked", "confirmed")),
        )
    )
    return res.rowcount > 0


async def undo_reject_for_source(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
) -> bool:
    snap = await _latest_snapshot_id(db, user_id=user_id)
    if snap is None:
        return False
    res = await db.execute(
        delete(SourceLibraryLink).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == snap,
            SourceLibraryLink.decision == "rejected",
        )
    )
    return res.rowcount > 0


async def undo_auto_match_for_source(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
) -> bool:
    """Remove auto (fuzzy run) link rows for this source on the latest library snapshot."""
    snap = await _latest_snapshot_id(db, user_id=user_id)
    if snap is None:
        return False
    res = await db.execute(
        delete(SourceLibraryLink).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == snap,
            SourceLibraryLink.decision == "auto",
        )
    )
    return res.rowcount > 0
