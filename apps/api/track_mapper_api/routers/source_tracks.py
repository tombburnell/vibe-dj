"""Source tracks from Postgres + match candidates API."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.models.library import LibraryTrack
from track_mapper_api.models.playlist import Playlist, source_track_playlists
from track_mapper_api.models.source import SourceTrack
from track_mapper_api.schemas import (
    AmazonLinkCandidateOut,
    ClearLocalFileOut,
    SetLocalFileIn,
    SetLocalFileOut,
    FindAmazonLinksOut,
    FindAmazonLinksRequest,
    LibraryCandidateOut,
    LibraryTrackOut,
    LocalScanMatchedOut,
    LocalScanOut,
    LocalScanRequest,
    LocalScanUnmatchedOut,
    MarkLinkBrokenIn,
    SourceTopMatchRowOut,
    SourceTopMatchesRequest,
    SourceTrackOut,
    SourceWishlistBatchIn,
    SourceWishlistBatchOut,
    YoutubeAudioDownloadIn,
)
from track_mapper_api.services.find_amazon_links import find_amazon_links_for_user
from track_mapper_api.services.web_search_service import display_link_title
from track_mapper_api.services.matching import (
    batch_top_match_by_source_id,
    resolve_snapshot_id,
    top_candidates_for_source,
)
from track_mapper_api.services.local_download_scan import (
    clear_source_local_file,
    run_local_download_scan,
    set_source_local_file,
)
from track_mapper_api.services.source_link_broken import mark_source_amazon_link_broken
from track_mapper_api.services.source_track_wishlist import set_wishlist_batch
from track_mapper_api.config import get_youtube_audio_dir
from track_mapper_api.services.youtube_audio_download import (
    copy_m4a_to_library_dir,
    download_and_transcode_youtube_m4a,
    relative_audio_path_from_absolute,
    source_track_contains_youtube_url,
)

router = APIRouter(prefix="/source-tracks", tags=["source-tracks"])
logger = logging.getLogger(__name__)


def _attachment_content_disposition(filename: str) -> str:
    ascii_fallback = (
        "".join(ch if ord(ch) < 128 and ch not in '\\"' else "_" for ch in filename).strip()
        or "track.m4a"
    )
    enc = quote(filename, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{enc}'

# Legacy rows stored ``matched_domain`` in ``artist``; UI joins title + artist with " — ".
_KNOWN_SITE_ARTIST_PLACEHOLDERS = frozenset(
    {
        "amazon.com",
        "soundcloud.com",
        "tidal.com",
        "beatport.com",
        "youtube.com",
        "youtu.be",
        "bandcamp.com",
    }
)


def _amazon_candidates_from_db(
    raw: list | None,
    *,
    st: SourceTrack | None = None,
) -> list[AmazonLinkCandidateOut]:
    """Normalize JSON candidates; legacy rows omit the primary URL from the array — prepend it."""
    if not raw:
        out: list[AmazonLinkCandidateOut] = []
    else:
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                cand = AmazonLinkCandidateOut.model_validate(item)
            except Exception:
                continue
            shown = display_link_title(cand.url, cand.title)
            artist = cand.artist
            if artist and artist.strip().lower() in _KNOWN_SITE_ARTIST_PLACEHOLDERS:
                artist = None
            updates: dict[str, str | None] = {}
            if shown is not None and shown != cand.title:
                updates["title"] = shown
            if artist != cand.artist:
                updates["artist"] = artist
            if updates:
                cand = cand.model_copy(update=updates)
            out.append(cand)

    primary_url = (st.amazon_url or "").strip() if st else ""
    if primary_url and not any(c.url == primary_url for c in out):
        shown_primary = display_link_title(primary_url, st.amazon_link_title)
        synthetic = AmazonLinkCandidateOut(
            url=primary_url,
            title=shown_primary,
            artist=None,
            match_score=st.amazon_link_match_score,
            price=st.amazon_price,
            broken=False,
        )
        out.insert(0, synthetic)
    return out


async def _playlist_membership_for_sources(
    db: AsyncSession,
    *,
    user_id: str,
    source_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[str]], dict[uuid.UUID, list[str]]]:
    """M2M playlist names and ids per source (explicit query; names sorted for stable order)."""
    if not source_ids:
        return {}, {}
    id_set = set(source_ids)
    res = await db.execute(
        select(source_track_playlists.c.source_track_id, Playlist.id, Playlist.name)
        .join(Playlist, Playlist.id == source_track_playlists.c.playlist_id)
        .where(
            Playlist.user_id == user_id,
            source_track_playlists.c.source_track_id.in_(source_ids),
        )
    )
    pairs_by: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
    for st_id, pl_id, pl_name in res.all():
        if st_id not in id_set:
            continue
        pairs_by.setdefault(st_id, []).append((pl_id, pl_name))

    names_by: dict[uuid.UUID, list[str]] = {}
    ids_by: dict[uuid.UUID, list[str]] = {}
    for sid in source_ids:
        pairs = sorted(pairs_by.get(sid, []), key=lambda x: (x[1], str(x[0])))
        names_by[sid] = [p[1] for p in pairs]
        ids_by[sid] = [str(p[0]) for p in pairs]
    return names_by, ids_by


def _st_out(
    st: SourceTrack,
    playlist_names: list[str],
    playlist_ids: list[str],
    *,
    lt: LibraryTrack | None = None,
    sc: float | None = None,
    top_match_library_track_id: str | None = None,
    top_match_is_picked: bool = False,
    is_rejected_no_match: bool = False,
    top_match_below_minimum: bool = False,
) -> SourceTrackOut:
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
        playlist_ids=playlist_ids,
        local_file_path=st.local_file_path,
        downloaded_at=st.downloaded_at,
        amazon_url=st.amazon_url,
        amazon_search_url=st.amazon_search_url,
        amazon_price=st.amazon_price,
        amazon_link_title=display_link_title(st.amazon_url, st.amazon_link_title),
        amazon_link_match_score=st.amazon_link_match_score,
        amazon_last_searched_at=st.amazon_last_searched_at,
        amazon_candidates=_amazon_candidates_from_db(st.amazon_candidates_json, st=st),
        created_at=st.created_at,
        updated_at=st.updated_at,
        top_match_title=lt.title if lt else None,
        top_match_artist=lt.artist if lt else None,
        top_match_score=sc,
        top_match_duration_ms=lt.duration_ms if lt else None,
        top_match_library_track_id=top_match_library_track_id,
        top_match_is_picked=top_match_is_picked,
        is_rejected_no_match=is_rejected_no_match,
        top_match_below_minimum=top_match_below_minimum,
    )


async def _source_track_out_one(
    db: AsyncSession,
    *,
    user_id: str,
    st: SourceTrack,
    min_score: float,
) -> SourceTrackOut:
    names_by_source, ids_by_source = await _playlist_membership_for_sources(
        db, user_id=user_id, source_ids=[st.id]
    )
    snap = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=None)
    best = await batch_top_match_by_source_id(
        db,
        user_id=user_id,
        library_snapshot_id=snap,
        tracks=[st],
        min_score=min_score,
    )
    lt, sc, is_picked, is_rejected, below_min = best.get(
        st.id, (None, None, False, False, False)
    )
    lid = str(lt.id) if lt else None
    return _st_out(
        st,
        names_by_source.get(st.id, []),
        ids_by_source.get(st.id, []),
        lt=lt,
        sc=sc,
        top_match_library_track_id=lid,
        top_match_is_picked=is_picked,
        is_rejected_no_match=is_rejected,
        top_match_below_minimum=below_min,
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
    min_score: float = Query(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Fuzzy floor for below-minimum flag (same as POST /top-matches).",
    ),
) -> list[SourceTrackOut]:
    result = await db.execute(
        select(SourceTrack)
        .where(SourceTrack.user_id == user_id)
        .order_by(SourceTrack.created_at.desc(), SourceTrack.id.desc())
    )
    tracks = list(result.scalars().all())
    source_ids = [t.id for t in tracks]
    names_by_source, ids_by_source = await _playlist_membership_for_sources(
        db, user_id=user_id, source_ids=source_ids
    )
    snap = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=None)
    best = await batch_top_match_by_source_id(
        db,
        user_id=user_id,
        library_snapshot_id=snap,
        tracks=tracks,
        min_score=min_score,
    )
    out: list[SourceTrackOut] = []
    for t in tracks:
        lt, sc, is_picked, is_rejected, below_min = best.get(
            t.id, (None, None, False, False, False)
        )
        lid = str(lt.id) if lt else None
        out.append(
            _st_out(
                t,
                names_by_source.get(t.id, []),
                ids_by_source.get(t.id, []),
                lt=lt,
                sc=sc,
                top_match_library_track_id=lid,
                top_match_is_picked=is_picked,
                is_rejected_no_match=is_rejected,
                top_match_below_minimum=below_min,
            )
        )
    return out


@router.post("/wishlist-batch", response_model=SourceWishlistBatchOut)
async def post_wishlist_batch(
    body: SourceWishlistBatchIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SourceWishlistBatchOut:
    n = await set_wishlist_batch(
        db,
        user_id=user_id,
        source_track_ids=list(body.source_track_ids),
        on_wishlist=body.on_wishlist,
    )
    return SourceWishlistBatchOut(updated_count=n)


@router.post("/{source_track_id}/mark-link-broken", response_model=SourceTrackOut)
async def post_mark_link_broken(
    source_track_id: str,
    body: MarkLinkBrokenIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    min_score: float = Query(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Same fuzzy floor as GET /source-tracks for top_match_below_minimum.",
    ),
) -> SourceTrackOut:
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    try:
        st = await mark_source_amazon_link_broken(
            db,
            user_id=user_id,
            source_track_id=sid,
            url=body.url,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await _source_track_out_one(db, user_id=user_id, st=st, min_score=min_score)


@router.post("/find-amazon-links", response_model=FindAmazonLinksOut)
async def post_find_amazon_links(
    body: FindAmazonLinksRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> FindAmazonLinksOut:
    """Find web links (Tidal / Amazon / SoundCloud) for Need (rejected) tracks; skips cached rows unless force."""
    ids: list[uuid.UUID] | None = None
    if body.source_track_ids:
        parsed: list[uuid.UUID] = []
        for s in body.source_track_ids[:200]:
            try:
                parsed.append(uuid.UUID(s))
            except ValueError:
                continue
        if not parsed:
            return FindAmazonLinksOut(
                searched_count=0,
                skipped_not_need_count=0,
                skipped_cached_count=0,
                error_count=0,
            )
        ids = parsed

    stats = await find_amazon_links_for_user(
        db,
        user_id=user_id,
        source_track_ids=ids,
        force=body.force,
        web_search_provider=body.web_search_provider,
    )
    await db.commit()
    return FindAmazonLinksOut(
        searched_count=stats.searched_count,
        skipped_not_need_count=stats.skipped_not_need_count,
        skipped_cached_count=stats.skipped_cached_count,
        error_count=stats.error_count,
    )


@router.post("/local-scan", response_model=LocalScanOut)
async def post_local_scan(
    body: LocalScanRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> LocalScanOut:
    """Match browser folder file paths to source rows (filename stem + fuzzy score)."""
    paths = [f.path for f in body.files]
    result = await run_local_download_scan(
        db,
        user_id=user_id,
        display_paths=paths,
        min_score=body.min_score,
    )
    return LocalScanOut(
        matched=[
            LocalScanMatchedOut(
                source_track_id=str(m.source_track_id),
                path=m.path,
                score=m.score,
                title=m.title,
                artist=m.artist,
            )
            for m in result.matched
        ],
        unmatched_files=result.unmatched_files,
        unmatched_details=[
            LocalScanUnmatchedOut(
                path=u.path,
                parsed_artist=u.parsed_artist,
                parsed_title=u.parsed_title,
                best_score=u.best_score,
                best_source_track_id=str(u.best_source_track_id)
                if u.best_source_track_id
                else None,
                best_source_artist=u.best_source_artist,
                best_source_title=u.best_source_title,
                below_threshold=u.below_threshold,
                source_claimed_by_other_file=u.source_claimed_by_other_file,
                best_source_already_has_file=u.best_source_already_has_file,
            )
            for u in result.unmatched_details
        ],
        skipped_non_audio=result.skipped_non_audio,
        min_score=body.min_score,
    )


@router.post("/{source_track_id}/youtube-audio")
async def post_source_youtube_audio(
    source_track_id: str,
    body: YoutubeAudioDownloadIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> FileResponse:
    """Transcode YouTube audio to AAC ``.m4a`` and stream it to the client (browser download).

    Optional ``persist``: copy the same file under ``YOUTUBE_AUDIO_DIR`` and set ``local_file_path``.
    """
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id == sid,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Source track not found")
    if not source_track_contains_youtube_url(row, url):
        raise HTTPException(
            status_code=400,
            detail="URL is not a YouTube link on this track",
        )

    artist = row.artist or ""
    title = row.title or ""
    loop = asyncio.get_running_loop()
    tmp_root = Path(tempfile.mkdtemp(prefix="yt-audio-"))

    def run_pipeline() -> Path:
        return download_and_transcode_youtube_m4a(
            artist=artist,
            title=title,
            page_url=url,
            work_dir=tmp_root,
        )

    try:
        m4a_path = await loop.run_in_executor(None, run_pipeline)
    except ValueError as e:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        shutil.rmtree(tmp_root, ignore_errors=True)
        logger.exception("YouTube audio download failed for source %s", sid)
        raise HTTPException(
            status_code=500,
            detail="YouTube download failed (check API logs and ffmpeg)",
        ) from e

    stream_path = m4a_path
    headers: dict[str, str] = {
        "Content-Disposition": _attachment_content_disposition(m4a_path.name),
    }

    if body.persist:
        final = copy_m4a_to_library_dir(m4a_path, get_youtube_audio_dir())
        rel = relative_audio_path_from_absolute(final)
        try:
            row2 = await set_source_local_file(
                db,
                user_id=user_id,
                source_track_id=sid,
                display_path=rel,
            )
        except ValueError as e:
            shutil.rmtree(tmp_root, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(e)) from e
        if row2 is None:
            shutil.rmtree(tmp_root, ignore_errors=True)
            raise HTTPException(status_code=404, detail="Source track not found")
        stream_path = final
        headers["X-Persisted-Path"] = rel

    return FileResponse(
        path=str(stream_path),
        media_type="audio/mp4",
        headers=headers,
        background=BackgroundTask(lambda: shutil.rmtree(tmp_root, ignore_errors=True)),
    )


@router.put("/{source_track_id}/local-file", response_model=SetLocalFileOut)
async def put_source_local_file(
    source_track_id: str,
    body: SetLocalFileIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SetLocalFileOut:
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    try:
        row = await set_source_local_file(
            db,
            user_id=user_id,
            source_track_id=sid,
            display_path=body.path,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if row is None:
        raise HTTPException(status_code=404, detail="Source track not found")
    return SetLocalFileOut(
        source_track_id=str(row.id),
        path=row.local_file_path or body.path.strip(),
        title=row.title,
        artist=row.artist,
    )


@router.delete("/{source_track_id}/local-file", response_model=ClearLocalFileOut)
async def delete_source_local_file(
    source_track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ClearLocalFileOut:
    try:
        sid = uuid.UUID(source_track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid source_track_id") from e
    ok = await clear_source_local_file(db, user_id=user_id, source_track_id=sid)
    if not ok:
        raise HTTPException(status_code=404, detail="Source track not found")
    return ClearLocalFileOut(cleared=True)


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
