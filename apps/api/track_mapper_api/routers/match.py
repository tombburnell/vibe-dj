from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.schemas import MatchRunOut
from track_mapper_api.services.matching import run_match_job
from track_mapper_api.services.source_link_actions import (
    pick_source_library_track,
    reject_source_no_match,
    undo_auto_match_for_source,
    undo_pick_for_source,
    undo_reject_for_source,
)

router = APIRouter(prefix="/match", tags=["match"])


class MatchRunIn(BaseModel):
    library_snapshot_id: str | None = Field(
        default=None,
        description="Snapshot to match against; latest for user when omitted.",
    )
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)


@router.post("/run", response_model=MatchRunOut)
async def run_match(
    body: MatchRunIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MatchRunOut:
    snap_uuid: uuid.UUID | None = None
    if body.library_snapshot_id:
        try:
            snap_uuid = uuid.UUID(body.library_snapshot_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid library_snapshot_id") from e

    sid, matched, skipped = await run_match_job(
        db,
        user_id=user_id,
        library_snapshot_id=snap_uuid,
        min_confidence=body.min_confidence,
    )
    return MatchRunOut(
        library_snapshot_id=str(sid) if sid else None,
        matched_count=matched,
        skipped_count=skipped,
    )


class MatchPickIn(BaseModel):
    source_track_id: str
    library_track_id: str
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)


class MatchRejectIn(BaseModel):
    source_track_id: str


class MatchActionOkOut(BaseModel):
    ok: bool = True


@router.post("/pick", response_model=MatchActionOkOut)
async def match_pick(
    body: MatchPickIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MatchActionOkOut:
    try:
        sid = uuid.UUID(body.source_track_id)
        lid = uuid.UUID(body.library_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid UUID") from e
    await pick_source_library_track(
        db,
        user_id=user_id,
        source_track_id=sid,
        library_track_id=lid,
        confidence=body.match_score,
    )
    return MatchActionOkOut()


@router.delete("/pick/{source_track_id}", response_model=MatchActionOkOut)
async def match_undo_pick(
    source_track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MatchActionOkOut:
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    ok = await undo_pick_for_source(db, user_id=user_id, source_track_id=sid)
    if not ok:
        raise HTTPException(status_code=404, detail="No pick to undo for this source")
    return MatchActionOkOut()


@router.post("/reject", response_model=MatchActionOkOut)
async def match_reject(
    body: MatchRejectIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MatchActionOkOut:
    try:
        sid = uuid.UUID(body.source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    await reject_source_no_match(db, user_id=user_id, source_track_id=sid)
    return MatchActionOkOut()


@router.delete("/reject/{source_track_id}", response_model=MatchActionOkOut)
async def match_undo_reject(
    source_track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MatchActionOkOut:
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    ok = await undo_reject_for_source(db, user_id=user_id, source_track_id=sid)
    if not ok:
        raise HTTPException(status_code=404, detail="No reject to undo for this source")
    return MatchActionOkOut()


@router.delete("/auto/{source_track_id}", response_model=MatchActionOkOut)
async def match_undo_auto(
    source_track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MatchActionOkOut:
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    ok = await undo_auto_match_for_source(db, user_id=user_id, source_track_id=sid)
    if not ok:
        raise HTTPException(status_code=404, detail="No auto match to undo for this source")
    return MatchActionOkOut()
