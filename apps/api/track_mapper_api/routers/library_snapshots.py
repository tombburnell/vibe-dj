from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.schemas import LibrarySnapshotImportOut
from track_mapper_api.services.library_import import import_rekordbox_tsv

router = APIRouter(prefix="/library-snapshots", tags=["library-snapshots"])


@router.post("/import", response_model=LibrarySnapshotImportOut)
async def import_library_snapshot(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    file: UploadFile = File(...),
    label: str | None = Form(None),
) -> LibrarySnapshotImportOut:
    raw = await file.read()
    snap_id, count = await import_rekordbox_tsv(
        db,
        user_id=user_id,
        file_bytes=raw,
        filename=file.filename,
        label=label,
    )
    return LibrarySnapshotImportOut(snapshot_id=str(snap_id), track_count=count)
