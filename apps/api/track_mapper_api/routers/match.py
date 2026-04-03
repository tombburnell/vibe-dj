from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.schemas import MatchRunOut
from track_mapper_api.services.matching import run_match_job

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
