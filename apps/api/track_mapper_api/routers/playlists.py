from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.schemas import PlaylistImportOut
from track_mapper_api.services.playlist_import import import_playlist_csv

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.post("/import", response_model=PlaylistImportOut)
async def import_playlist(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    file: UploadFile = File(...),
    playlist_name: str = Form(...),
    import_source: str = Form("chosic_csv"),
) -> PlaylistImportOut:
    raw = await file.read()
    pl_id, linked, new_src = await import_playlist_csv(
        db,
        user_id=user_id,
        file_bytes=raw,
        playlist_name=playlist_name,
        import_source=import_source or "chosic_csv",
    )
    return PlaylistImportOut(
        playlist_id=str(pl_id),
        rows_linked=linked,
        new_source_tracks=new_src,
    )
