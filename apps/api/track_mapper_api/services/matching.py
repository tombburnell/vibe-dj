from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.library import LibrarySnapshot, LibraryTrack
from track_mapper_api.models.link import SourceLibraryLink
from track_mapper_api.models.source import SourceTrack
from track_mapper_api.repo_src_path import ensure_repo_root_on_path
from track_mapper_api.services.source_link_actions import (
    is_source_rejected_for_snapshot,
    link_mode_for_source_snapshot,
)


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


def pair_scores_for_source(
    st: SourceTrack,
    index,
    id_by_rb: dict[str, uuid.UUID],
    rows: list[LibraryTrack],
    *,
    lt_by_id: dict[uuid.UUID, LibraryTrack] | None = None,
) -> list[tuple[LibraryTrack, float]]:
    """All scored library candidates for one source (same rules as match job), sorted by score desc."""
    ensure_repo_root_on_path()
    from src.track_matching import calculate_match_score
    from src.track_normalizer import create_all_tokens

    lookup = lt_by_id if lt_by_id is not None else {r.id: r for r in rows}

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
        lt = lookup.get(lt_id)
        if lt is not None:
            scored.append((lt, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


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
            SourceLibraryLink.decision.in_(("confirmed", "picked")),
        )
    )
    if res.first() is not None:
        return True
    return await is_source_rejected_for_snapshot(
        db,
        user_id=user_id,
        source_track_id=source_track_id,
        library_snapshot_id=library_snapshot_id,
    )


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


async def _library_track_ids_excluded_from_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Active match links for this source+snapshot — do not list again as candidates."""
    res = await db.execute(
        select(SourceLibraryLink.library_track_id).where(
            SourceLibraryLink.user_id == user_id,
            SourceLibraryLink.source_track_id == source_track_id,
            SourceLibraryLink.library_snapshot_id == library_snapshot_id,
            SourceLibraryLink.library_track_id.isnot(None),
            SourceLibraryLink.decision.in_(("picked", "confirmed", "auto")),
        )
    )
    return {row[0] for row in res.all() if row[0] is not None}


async def top_candidates_for_source(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    library_snapshot_id: uuid.UUID,
    limit: int = 8,
    min_score: float = 0.0,
) -> list[tuple[LibraryTrack, float]]:
    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.id == source_track_id,
            SourceTrack.user_id == user_id,
        )
    )
    st = res.scalar_one_or_none()
    if st is None:
        return []

    mode, _ = await link_mode_for_source_snapshot(
        db,
        user_id=user_id,
        source_track_id=source_track_id,
        library_snapshot_id=library_snapshot_id,
    )
    if mode == "rejected":
        return []

    exclude_lt = await _library_track_ids_excluded_from_candidates(
        db,
        user_id=user_id,
        source_track_id=source_track_id,
        library_snapshot_id=library_snapshot_id,
    )

    rows = await load_library_rows_for_snapshot(
        db, user_id=user_id, library_snapshot_id=library_snapshot_id
    )
    if not rows:
        return []

    index, id_by_rb = _build_index(rows)
    lt_by_id = {r.id: r for r in rows}
    scored = pair_scores_for_source(st, index, id_by_rb, rows, lt_by_id=lt_by_id)
    filtered = [
        (lt, s)
        for lt, s in scored
        if s >= min_score and lt.id not in exclude_lt
    ]
    return filtered[:limit]


async def batch_top_match_by_source_id(
    db: AsyncSession,
    *,
    user_id: str,
    library_snapshot_id: uuid.UUID | None,
    tracks: list[SourceTrack],
    min_score: float = 0.0,
) -> dict[uuid.UUID, tuple[LibraryTrack | None, float | None, bool, bool, bool]]:
    """lt, score, is_picked, is_rejected, below_minimum (fuzzy best < min_score but candidate exists)."""
    empty = (None, None, False, False, False)
    if library_snapshot_id is None or not tracks:
        return {t.id: empty for t in tracks}

    rows = await load_library_rows_for_snapshot(
        db, user_id=user_id, library_snapshot_id=library_snapshot_id
    )
    if not rows:
        return {t.id: empty for t in tracks}

    index, id_by_rb = _build_index(rows)
    lt_by_id = {r.id: r for r in rows}
    out: dict[uuid.UUID, tuple[LibraryTrack | None, float | None, bool, bool, bool]] = {}
    for st in tracks:
        mode, link = await link_mode_for_source_snapshot(
            db,
            user_id=user_id,
            source_track_id=st.id,
            library_snapshot_id=library_snapshot_id,
        )
        if mode == "rejected":
            out[st.id] = (None, None, False, True, False)
            continue
        if mode == "picked" and link is not None and link.library_track_id is not None:
            lt = lt_by_id.get(link.library_track_id)
            if lt is not None:
                out[st.id] = (lt, link.confidence, True, False, False)
            else:
                out[st.id] = empty
            continue

        pairs = pair_scores_for_source(
            st, index, id_by_rb, rows, lt_by_id=lt_by_id
        )
        best = pairs[0] if pairs else (None, None)
        if best[0] is None:
            out[st.id] = empty
        elif best[1] is not None and best[1] < min_score:
            # UI shows flag only in Best match cell — no track/score payload
            out[st.id] = (None, None, False, False, True)
        else:
            out[st.id] = (best[0], best[1], False, False, False)
    return out


async def run_match_job(
    db: AsyncSession,
    *,
    user_id: str,
    library_snapshot_id: uuid.UUID | None,
    min_confidence: float = 0.6,
) -> tuple[uuid.UUID | None, int, int]:
    """Write auto links for source_tracks against the given (or latest) snapshot."""
    ensure_repo_root_on_path()

    sid = await resolve_snapshot_id(db, user_id=user_id, snapshot_id=library_snapshot_id)
    if sid is None:
        return None, 0, 0

    rows = await load_library_rows_for_snapshot(db, user_id=user_id, library_snapshot_id=sid)
    if not rows:
        return sid, 0, 0

    index, id_by_rb = _build_index(rows)
    lt_by_id = {r.id: r for r in rows}
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

        pairs = pair_scores_for_source(
            st, index, id_by_rb, rows, lt_by_id=lt_by_id
        )
        if not pairs:
            continue
        best_lt, best_score = pairs[0]
        if best_score < min_confidence:
            continue

        db.add(
            SourceLibraryLink(
                id=uuid.uuid4(),
                user_id=user_id,
                source_track_id=st.id,
                library_track_id=best_lt.id,
                library_snapshot_id=sid,
                decision="auto",
                confidence=best_score,
                rank=1,
                rejected_through_snapshot_id=None,
            )
        )
        matched += 1

    return sid, matched, skipped
