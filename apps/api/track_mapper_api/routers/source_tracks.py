"""Source tracks from Postgres + match candidates API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.models.library import LibraryTrack
from track_mapper_api.models.source import SourceTrack
from track_mapper_api.schemas import LibraryCandidateOut, LibraryTrackOut, SourceTrackOut
from track_mapper_api.services.matching import resolve_snapshot_id, top_candidates_for_source

router = APIRouter(prefix="/source-tracks", tags=["source-tracks"])


def _st_out(st: SourceTrack) -> SourceTrackOut:
    names = sorted({p.name for p in st.playlists})
    return SourceTrackOut(
        id=str(st.id),
        user_id=st.user_id,
        source_kind=st.source_kind,
        title=st.title,
        artist=st.artist,
        album=st.album,
        duration_ms=st.duration_ms,
        spotify_id=st.spotify_id,
        spotify_url=st.spotify_url,
        on_wishlist=st.on_wishlist,
        playlist_names=names,
        local_file_path=st.local_file_path,
        downloaded_at=st.downloaded_at,
        amazon_url=st.amazon_url,
        amazon_search_url=st.amazon_search_url,
        created_at=st.created_at,
        updated_at=st.updated_at,
    )


def _lt_core_out(lt: LibraryTrack) -> LibraryTrackOut:
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


@router.get("", response_model=list[SourceTrackOut])
async def list_source_tracks(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[SourceTrackOut]:
    result = await db.execute(
        select(SourceTrack)
        .where(SourceTrack.user_id == user_id)
        .options(selectinload(SourceTrack.playlists))
        .order_by(SourceTrack.updated_at.desc())
    )
    tracks = result.scalars().unique().all()
    return [_st_out(t) for t in tracks]


@router.get("/{source_track_id}/candidates", response_model=list[LibraryCandidateOut])
async def list_match_candidates(
    source_track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    snapshot_id: str | None = Query(
        default=None,
        description="Library snapshot UUID; defaults to latest for this user.",
    ),
    limit: int = Query(default=8, ge=1, le=50),
) -> list[LibraryCandidateOut]:
    try:
        st_uuid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e

    snap_uuid: uuid.UUID | None = None
    if snapshot_id is not None:
        try:
            snap_uuid = uuid.UUID(snapshot_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid snapshot_id") from e

    resolved = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=snap_uuid)
    if resolved is None:
        return []

    pairs = await top_candidates_for_source(
        db,
        user_id=user_id,
        source_track_id=st_uuid,
        library_snapshot_id=resolved,
        limit=limit,
    )
    return [
        LibraryCandidateOut(
            **_lt_core_out(lt).model_dump(),
            match_score=score,
        )
        for lt, score in pairs
    ]
