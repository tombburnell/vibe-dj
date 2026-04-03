"""Library tracks list from Postgres (latest snapshot by default)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.models.library import LibraryTrack
from track_mapper_api.schemas import LibraryTrackOut, LibraryTrackPageOut
from track_mapper_api.services.library_list import DEFAULT_PAGE_SIZE, load_library_tracks_page
from track_mapper_api.services.matching import resolve_snapshot_id

router = APIRouter(prefix="/library-tracks", tags=["library-tracks"])


def _lt_out(lt: LibraryTrack) -> LibraryTrackOut:
    return LibraryTrackOut(
        id=str(lt.id),
        user_id=lt.user_id,
        library_snapshot_id=str(lt.library_snapshot_id),
        title=lt.title,
        artist=lt.artist,
        album=lt.album,
        duration_ms=lt.duration_ms,
        file_path=lt.file_path,
        bpm=lt.bpm,
        musical_key=lt.musical_key,
        genre=lt.genre,
        created_at=lt.created_at,
    )


@router.get("", response_model=LibraryTrackPageOut)
async def list_library_tracks(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    snapshot_id: str | None = Query(
        default=None,
        description="Library snapshot UUID; defaults to latest import for this user.",
    ),
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=500,
        description="Page size (keyset pagination by file_path, id).",
    ),
    cursor: str | None = Query(
        default=None,
        description="Opaque cursor from the previous page's next_cursor.",
    ),
) -> LibraryTrackPageOut:
    snap_uuid: uuid.UUID | None = None
    if snapshot_id is not None:
        try:
            snap_uuid = uuid.UUID(snapshot_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid snapshot_id") from e

    resolved = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=snap_uuid)
    if resolved is None:
        return LibraryTrackPageOut(items=[], next_cursor=None)

    try:
        rows, next_c = await load_library_tracks_page(
            db,
            user_id=user_id,
            library_snapshot_id=resolved,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid cursor") from e

    return LibraryTrackPageOut(items=[_lt_out(lt) for lt in rows], next_cursor=next_c)
