from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.models.playlist import Playlist
from track_mapper_api.schemas import PlaylistImportOut, PlaylistOut, SpotifyPlaylistImportIn
from track_mapper_api.services.playlist_import import import_playlist_csv
from track_mapper_api.services.spotify_playlist_import import import_public_spotify_playlist
from track_mapper_api.services.spotify_oauth_service import SpotifyNotConnectedError
from track_mapper_api.services.spotify_web_api import SpotifyPlaylistParseError, SpotifyWebApiError

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=list[PlaylistOut])
async def list_playlists(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[PlaylistOut]:
    res = await db.execute(
        select(Playlist)
        .where(Playlist.user_id == user_id)
        .order_by(Playlist.name.asc(), Playlist.created_at.desc())
    )
    rows = list(res.scalars().all())
    return [
        PlaylistOut(
            id=str(p.id),
            name=p.name,
            import_source=p.import_source,
            created_at=p.created_at,
        )
        for p in rows
    ]


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Response:
    try:
        pl_uuid = uuid.UUID(playlist_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid playlist_id") from e

    result = await db.execute(
        delete(Playlist).where(Playlist.id == pl_uuid, Playlist.user_id == user_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return Response(status_code=204)


@router.post("/import", response_model=PlaylistImportOut)
async def import_playlist(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    file: UploadFile = File(...),
    playlist_name: str | None = Form(None),
    client_filename: str | None = Form(None),
    import_source: str = Form("chosic_csv"),
) -> PlaylistImportOut:
    raw = await file.read()
    upload_filename = file.filename
    if not (upload_filename and upload_filename.strip()) and client_filename and client_filename.strip():
        upload_filename = client_filename.strip()
    pl_id, linked, new_src = await import_playlist_csv(
        db,
        user_id=user_id,
        file_bytes=raw,
        playlist_name=playlist_name,
        upload_filename=upload_filename,
        import_source=import_source or "chosic_csv",
    )
    return PlaylistImportOut(
        playlist_id=str(pl_id),
        rows_linked=linked,
        new_source_tracks=new_src,
    )


@router.post("/import-spotify", response_model=PlaylistImportOut)
async def import_spotify_playlist(
    body: SpotifyPlaylistImportIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> PlaylistImportOut:
    raw = body.playlist_id_or_url.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="playlist_id_or_url is empty.")
    try:
        pl_id, linked, new_src = await import_public_spotify_playlist(
            db,
            user_id=user_id,
            playlist_id_or_url=raw,
            playlist_name_override=body.playlist_name,
        )
    except SpotifyPlaylistParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SpotifyNotConnectedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except SpotifyWebApiError as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=str(e),
            ) from e
        if e.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=502,
            detail=str(e),
        ) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PlaylistImportOut(
        playlist_id=str(pl_id),
        rows_linked=linked,
        new_source_tracks=new_src,
    )
