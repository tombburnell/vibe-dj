from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.library import LibrarySnapshot, LibraryTrack
from track_mapper_api.models.link import SourceLibraryLink
from track_mapper_api.models.source import SourceTrack
from track_mapper_api.repo_src_path import ensure_repo_root_on_path


def _library_rows_to_rb_tracks(rows: list[LibraryTrack]):
    ensure_repo_root_on_path()
    from src.rekordbox_tsv_parser import RekordboxTSVTrack

    rb_list: list = []
    id_by_rb: dict[str, uuid.UUID] = {}
    for lt in rows:
        rb = RekordboxTSVTrack(
            title=lt.title,
            artist=lt.artist,
            album=lt.album,
            genre=lt.genre,
            bpm=lt.bpm,
            key=lt.musical_key,
            duration_ms=lt.duration_ms,
            file_path=lt.file_path or "",
        )
        rb_list.append(rb)
        id_by_rb[rb.rb_track_id] = lt.id
    return rb_list, id_by_rb


def _build_index(rows: list[LibraryTrack]):
    ensure_repo_root_on_path()
    from src.rekordbox_index import RekordboxIndex

    rb_list, id_by_rb = _library_rows_to_rb_tracks(rows)
    index = RekordboxIndex(rb_list)
    return index, id_by_rb


def _source_as_match_lhs(st: SourceTrack):
    return SimpleNamespace(
        title=st.title,
        artist=st.artist,
        album=st.album or "",
        duration_ms=st.duration_ms,
    )


async def _should_skip_source(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
) -> bool:
    res = await db.execute(
        select(SourceLibraryLink.id).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == library_snapshot_id,
            SourceLibraryLink.decision.in_(("confirmed", "picked", "rejected")),
        )
    )
    return res.first() is not None


async def resolve_snapshot_id(
    db: AsyncSession,
    *,
    user_id: str,
    snapshot_id: uuid.UUID | None,
) -> uuid.UUID | None:
    if snapshot_id is not None:
        res = await db.execute(
            select(LibrarySnapshot.id).where(
                LibrarySnapshot.user_id == user_id,
                LibrarySnapshot.id == snapshot_id,
            )
        )
        return res.scalar_one_or_none()

    res = await db.execute(
        select(LibrarySnapshot.id)
        .where(LibrarySnapshot.user_id == user_id)
        .order_by(LibrarySnapshot.imported_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def load_library_rows_for_snapshot(
    db: AsyncSession, *, user_id: str, library_snapshot_id: uuid.UUID
) -> list[LibraryTrack]:
    result = await db.execute(
        select(LibraryTrack)
        .where(
            LibraryTrack.user_id == user_id,
            LibraryTrack.library_snapshot_id == library_snapshot_id,
        )
        .order_by(LibraryTrack.file_path, LibraryTrack.id)
    )
    return list(result.scalars().all())


async def top_candidates_for_source(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
    limit: int = 8,
) -> list[tuple[LibraryTrack, float]]:
    ensure_repo_root_on_path()
    from src.track_matching import calculate_match_score
    from src.track_normalizer import create_all_tokens

    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.id == source_track_id,
            SourceTrack.user_id == user_id,
        )
    )
    st = res.scalar_one_or_none()
    if st is None:
        return []

    rows = await load_library_rows_for_snapshot(
        db, user_id=user_id, library_snapshot_id=library_snapshot_id
    )
    if not rows:
        return []

    index, id_by_rb = _build_index(rows)
    lhs = _source_as_match_lhs(st)
    tokens = create_all_tokens(st.title, st.artist, st.album or "")
    candidate_ids = index.get_candidates(tokens, max_candidates=40)

    scored: list[tuple[LibraryTrack, float]] = []
    seen_lt: set[uuid.UUID] = set()
    for rb_id in candidate_ids:
        rb = index.get_track(rb_id)
        if rb is None:
            continue
        lt_id = id_by_rb.get(rb_id)
        if lt_id is None or lt_id in seen_lt:
            continue
        seen_lt.add(lt_id)
        score = float(calculate_match_score(lhs, rb))
        lt = next((r for r in rows if r.id == lt_id), None)
        if lt is not None:
            scored.append((lt, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


async def run_match_job(
    db: AsyncSession,
    *,
    user_id: str,
    library_snapshot_id: uuid.UUID | None,
    min_confidence: float = 0.6,
) -> tuple[uuid.UUID | None, int, int]:
    """Write auto links for source_tracks against the given (or latest) snapshot."""
    ensure_repo_root_on_path()
    from src.track_matching import calculate_match_score
    from src.track_normalizer import create_all_tokens

    sid = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=library_snapshot_id)
    if sid is None:
        return None, 0, 0

    rows = await load_library_rows_for_snapshot(db, user_id=user_id, library_snapshot_id=sid)
    if not rows:
        return sid, 0, 0

    index, id_by_rb = _build_index(rows)
    src_res = await db.execute(select(SourceTrack).where(SourceTrack.user_id == user_id))
    sources = list(src_res.scalars().all())

    matched = 0
    skipped = 0

    for st in sources:
        if await _should_skip_source(
            db,
            user_id=user_id,
            source_track_id=st.id,
            library_snapshot_id=sid,
        ):
            skipped += 1
            continue

        await db.execute(
            delete(SourceLibraryLink).where(
                SourceLibraryLink.user_id == user_id,
                SourceLibraryLink.source_track_id == st.id,
                SourceLibraryLink.library_snapshot_id == sid,
                SourceLibraryLink.decision == "auto",
            )
        )
        await db.flush()

        lhs = _source_as_match_lhs(st)
        tokens = create_all_tokens(st.title, st.artist, st.album or "")
        candidate_ids = index.get_candidates(tokens, max_candidates=40)

        best_rb_id = None
        best_score = 0.0
        for rb_id in candidate_ids:
            rb = index.get_track(rb_id)
            if rb is None:
                continue
            score = float(calculate_match_score(lhs, rb))
            if score > best_score:
                best_score = score
                best_rb_id = rb_id

        if best_rb_id is None or best_score < min_confidence:
            continue

        lt_id = id_by_rb.get(best_rb_id)
        if lt_id is None:
            continue

        db.add(
            SourceLibraryLink(
                id=uuid.uuid4(),
                user_id=user_id,
                source_track_id=st.id,
                library_track_id=lt_id,
                library_snapshot_id=sid,
                decision="auto",
                confidence=best_score,
                rank=1,
                rejected_through_snapshot_id=None,
            )
        )
        matched += 1

    return sid, matched, skipped
