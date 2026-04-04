"""Source tracks from Postgres + match candidates API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.models.library import LibraryTrack
from track_mapper_api.models.playlist import Playlist, source_track_playlists
from track_mapper_api.models.source import SourceTrack
from track_mapper_api.schemas import (
    LibraryCandidateOut,
    LibraryTrackOut,
    SourceTopMatchRowOut,
    SourceTopMatchesRequest,
    SourceTrackOut,
)
from track_mapper_api.services.matching import (
    batch_top_match_by_source_id,
    resolve_snapshot_id,
    top_candidates_for_source,
)

router = APIRouter(prefix="/source-tracks", tags=["source-tracks"])


async def _playlist_names_for_sources(
    db: AsyncSession,
    *,
    user_id: str,
    source_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[str]]:
    """M2M playlist names per source (explicit query; avoids async ORM collection edge cases)."""
    if not source_ids:
        return {}
    res = await db.execute(
        select(source_track_playlists.c.source_track_id, Playlist.name)
        .join(Playlist, Playlist.id == source_track_playlists.c.playlist_id)
        .where(
            Playlist.user_id == user_id,
            source_track_playlists.c.source_track_id.in_(source_ids),
        )
    )
    buckets: dict[uuid.UUID, set[str]] = {sid: set() for sid in source_ids}
    for st_id, pl_name in res.all():
        if st_id in buckets:
            buckets[st_id].add(pl_name)
    return {sid: sorted(names) for sid, names in buckets.items()}


def _st_out(
    st: SourceTrack,
    playlist_names: list[str],
    top: tuple[LibraryTrack | None, float | None] | None = None,
) -> SourceTrackOut:
    lt, sc = top if top else (None, None)
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
        playlist_names=playlist_names,
        local_file_path=st.local_file_path,
        downloaded_at=st.downloaded_at,
        amazon_url=st.amazon_url,
        amazon_search_url=st.amazon_search_url,
        created_at=st.created_at,
        updated_at=st.updated_at,
        top_match_title=lt.title if lt else None,
        top_match_artist=lt.artist if lt else None,
        top_match_score=sc,
        top_match_duration_ms=lt.duration_ms if lt else None,
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
        .order_by(SourceTrack.updated_at.desc())
    )
    tracks = list(result.scalars().all())
    source_ids = [t.id for t in tracks]
    names_by_source = await _playlist_names_for_sources(
        db, user_id=user_id, source_ids=source_ids
    )
    return [_st_out(t, names_by_source.get(t.id, []), None) for t in tracks]


@router.post("/top-matches", response_model=list[SourceTopMatchRowOut])
async def post_source_top_matches(
    body: SourceTopMatchesRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[SourceTopMatchRowOut]:
    """Best match for a subset of sources (e.g. visible grid rows). Max 100 ids per call."""
    raw_ids: list[uuid.UUID] = []
    for s in body.source_track_ids[:100]:
        try:
            raw_ids.append(uuid.UUID(s))
        except ValueError:
            continue
    if not raw_ids:
        return []

    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id.in_(raw_ids),
        )
    )
    tracks = list(res.scalars().all())
    if not tracks:
        return []

    snap = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=None)
    best = await batch_top_match_by_source_id(
        db,
        user_id=user_id,
        library_snapshot_id=snap,
        tracks=tracks,
        min_score=body.min_score,
    )
    out: list[SourceTopMatchRowOut] = []
    for t in tracks:
        lt, sc, is_picked, is_rejected, below_min = best.get(
            t.id, (None, None, False, False, False)
        )
        out.append(
            SourceTopMatchRowOut(
                source_track_id=str(t.id),
                top_match_library_track_id=str(lt.id) if lt else None,
                top_match_title=lt.title if lt else None,
                top_match_artist=lt.artist if lt else None,
                top_match_score=sc,
                top_match_duration_ms=lt.duration_ms if lt else None,
                top_match_is_picked=is_picked,
                is_rejected_no_match=is_rejected,
                top_match_below_minimum=below_min,
            )
        )
    return out


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
    min_score: float = Query(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum match score for candidates (0.4 = 40%).",
    ),
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
        min_score=min_score,
    )
    return [
        LibraryCandidateOut(
            **_lt_core_out(lt).model_dump(),
            match_score=score,
            title_match_score=title_s,
            artist_match_score=artist_s,
        )
        for lt, score, title_s, artist_s in pairs
    ]
