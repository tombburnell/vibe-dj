"""Match browser-reported file paths to source_tracks (local download markers).

Filename parsing and fuzzy scoring mirror legacy ``src/download_scanner.py`` (stem only,
``rapidfuzz.fuzz.token_sort_ratio``, default floor 80). ID3 tags are not read here; see plan
for a future upgrade using the same API payload shape with richer fields.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.source import SourceTrack

_MUSIC_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".flac",
        ".m4a",
        ".wav",
        ".aac",
        ".ogg",
        ".wma",
        ".webm",
        ".opus",
    }
)


def stem_from_display_path(path: str) -> str:
    """Last path segment without extension (POSIX or backslash)."""
    normalized = path.replace("\\", "/").strip().strip("/")
    if not normalized:
        return ""
    name = normalized.split("/")[-1]
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name


def parse_artist_title_from_stem(stem: str) -> tuple[str | None, str | None]:
    """Same rules as ``download_scanner.scan_directory`` (filename stem only)."""
    if not stem:
        return (None, None)
    if " - " in stem:
        parts = stem.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else stem
        return (artist, title or None)
    if "/" in stem:
        parts = stem.rsplit("/", 1)
        artist = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else stem
        return (artist, title or None)
    return (None, stem.strip() or None)


def is_audio_display_path(path: str) -> bool:
    lower = path.lower().strip()
    return any(lower.endswith(ext) for ext in _MUSIC_EXTENSIONS)


def _normalize_for_match(s: str) -> str:
    """Casefold, unify dashes, drop punctuation so TEED ≈ T.E.E.D. for fuzzy compare."""
    t = s.strip().casefold()
    t = t.replace("—", " ").replace("–", "-")
    t = re.sub(r"[^\w\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _source_search_string(st: SourceTrack) -> str:
    return f"{_normalize_for_match(st.artist)} {_normalize_for_match(st.title)}"


def score_path_against_source(path: str, st: SourceTrack) -> float:
    """0–100 fuzzy score; 0 if path cannot yield a title."""
    stem = stem_from_display_path(path)
    artist, title = parse_artist_title_from_stem(stem)
    if not title:
        return 0.0
    if artist:
        file_search = f"{_normalize_for_match(artist)} {_normalize_for_match(title)}"
    else:
        file_search = _normalize_for_match(title)
    db_search = _source_search_string(st)
    score = float(fuzz.token_sort_ratio(file_search, db_search))
    score = max(score, float(fuzz.token_set_ratio(file_search, db_search)))
    if not artist:
        title_score = float(
            fuzz.token_sort_ratio(
                _normalize_for_match(title),
                _normalize_for_match(st.title),
            )
        )
        score = max(score, title_score * 0.8)
    return score


def _has_local_file(st: SourceTrack) -> bool:
    return bool((st.local_file_path or "").strip())


def _best_source_for_path(
    path: str, sources: list[SourceTrack]
) -> tuple[SourceTrack | None, float]:
    best_st: SourceTrack | None = None
    best_sc = 0.0
    for st in sources:
        sc = score_path_against_source(path, st)
        if sc > best_sc:
            best_sc = sc
            best_st = st
    return (best_st, best_sc)


def _best_eligible_score(path: str, eligible: list[SourceTrack]) -> float:
    _, sc = _best_source_for_path(path, eligible)
    return sc


@dataclass(frozen=True)
class LocalScanMatch:
    source_track_id: uuid.UUID
    path: str
    score: float
    title: str
    artist: str


@dataclass(frozen=True)
class LocalScanUnmatchedDetail:
    path: str
    parsed_artist: str | None
    parsed_title: str | None
    best_score: float
    best_source_track_id: uuid.UUID | None
    best_source_artist: str | None
    best_source_title: str | None
    # best fuzzy score < min_score (no eligible pair strong enough).
    below_threshold: bool
    # best pair met threshold but that source was greedy-matched to another file in this scan.
    source_claimed_by_other_file: bool
    # best overall source already had a local path before this scan (excluded from auto-match pool).
    best_source_already_has_file: bool


@dataclass(frozen=True)
class LocalScanResult:
    matched: list[LocalScanMatch]
    unmatched_files: list[str]
    unmatched_details: list[LocalScanUnmatchedDetail]
    skipped_non_audio: int


async def run_local_download_scan(
    db: AsyncSession,
    *,
    user_id: str,
    display_paths: list[str],
    min_score: float = 80.0,
) -> LocalScanResult:
    """Greedy many-to-one assignment: each source at most one file, each file at most one source."""
    audio_paths: list[str] = []
    skipped_non_audio = 0
    seen_paths: set[str] = set()
    for p in display_paths:
        raw = (p or "").strip()
        if not raw or raw in seen_paths:
            continue
        seen_paths.add(raw)
        if not is_audio_display_path(raw):
            skipped_non_audio += 1
            continue
        audio_paths.append(raw)

    if not audio_paths:
        return LocalScanResult(
            matched=[],
            unmatched_files=[],
            unmatched_details=[],
            skipped_non_audio=skipped_non_audio,
        )

    res = await db.execute(
        select(SourceTrack).where(SourceTrack.user_id == user_id),
    )
    all_sources = list(res.scalars().all())
    initial_has_file: dict[uuid.UUID, bool] = {
        st.id: _has_local_file(st) for st in all_sources
    }
    eligible = [st for st in all_sources if not initial_has_file[st.id]]

    if not all_sources:
        empty_details: list[LocalScanUnmatchedDetail] = []
        for path in audio_paths:
            stem = stem_from_display_path(path)
            pa, pt = parse_artist_title_from_stem(stem)
            empty_details.append(
                LocalScanUnmatchedDetail(
                    path=path,
                    parsed_artist=pa,
                    parsed_title=pt,
                    best_score=0.0,
                    best_source_track_id=None,
                    best_source_artist=None,
                    best_source_title=None,
                    below_threshold=True,
                    source_claimed_by_other_file=False,
                    best_source_already_has_file=False,
                )
            )
        return LocalScanResult(
            matched=[],
            unmatched_files=list(audio_paths),
            unmatched_details=empty_details,
            skipped_non_audio=skipped_non_audio,
        )

    if not eligible:
        unmatched_details_no_eligible: list[LocalScanUnmatchedDetail] = []
        for path in audio_paths:
            stem = stem_from_display_path(path)
            pa, pt = parse_artist_title_from_stem(stem)
            best_st, best_sc = _best_source_for_path(path, all_sources)
            unmatched_details_no_eligible.append(
                LocalScanUnmatchedDetail(
                    path=path,
                    parsed_artist=pa,
                    parsed_title=pt,
                    best_score=best_sc,
                    best_source_track_id=best_st.id if best_st else None,
                    best_source_artist=best_st.artist if best_st else None,
                    best_source_title=best_st.title if best_st else None,
                    below_threshold=True,
                    source_claimed_by_other_file=False,
                    best_source_already_has_file=bool(
                        best_st and initial_has_file.get(best_st.id, False)
                    ),
                )
            )
        return LocalScanResult(
            matched=[],
            unmatched_files=list(audio_paths),
            unmatched_details=unmatched_details_no_eligible,
            skipped_non_audio=skipped_non_audio,
        )

    edges: list[tuple[float, str, uuid.UUID]] = []
    for path in audio_paths:
        best_sid: uuid.UUID | None = None
        best_sc = 0.0
        for st in eligible:
            sc = score_path_against_source(path, st)
            if sc >= min_score and sc > best_sc:
                best_sc = sc
                best_sid = st.id
        if best_sid is not None:
            edges.append((best_sc, path, best_sid))

    edges.sort(key=lambda t: t[0], reverse=True)
    used_files: set[str] = set()
    used_sources: set[uuid.UUID] = set()
    assignments: list[tuple[float, str, uuid.UUID]] = []
    for sc, path, sid in edges:
        if path in used_files or sid in used_sources:
            continue
        used_files.add(path)
        used_sources.add(sid)
        assignments.append((sc, path, sid))

    matched_paths = {p for _, p, _ in assignments}
    unmatched = [p for p in audio_paths if p not in matched_paths]
    used_source_to_path: dict[uuid.UUID, str] = {
        sid: pth for _sc, pth, sid in assignments
    }

    unmatched_details: list[LocalScanUnmatchedDetail] = []
    for path in unmatched:
        best_st, best_sc = _best_source_for_path(path, all_sources)
        best_eligible_sc = _best_eligible_score(path, eligible)
        stem = stem_from_display_path(path)
        pa, pt = parse_artist_title_from_stem(stem)
        below = best_eligible_sc < min_score
        already_file = bool(best_st and initial_has_file.get(best_st.id, False))
        claimed = False
        if (
            best_st is not None
            and best_sc >= min_score
            and not already_file
            and best_st.id in used_source_to_path
        ):
            assigned_path = used_source_to_path.get(best_st.id)
            claimed = assigned_path is not None and assigned_path != path
        unmatched_details.append(
            LocalScanUnmatchedDetail(
                path=path,
                parsed_artist=pa,
                parsed_title=pt,
                best_score=best_sc,
                best_source_track_id=best_st.id if best_st else None,
                best_source_artist=best_st.artist if best_st else None,
                best_source_title=best_st.title if best_st else None,
                below_threshold=below,
                source_claimed_by_other_file=claimed,
                best_source_already_has_file=already_file,
            )
        )

    now = datetime.now(timezone.utc)
    id_to_row = {st.id: st for st in eligible}
    matched: list[LocalScanMatch] = []
    for sc, path, sid in assignments:
        row = id_to_row.get(sid)
        if row is None:
            continue
        row.local_file_path = path
        row.downloaded_at = now
        row.manual_dl = False
        matched.append(
            LocalScanMatch(
                source_track_id=sid,
                path=path,
                score=sc,
                title=row.title,
                artist=row.artist,
            )
        )

    return LocalScanResult(
        matched=matched,
        unmatched_files=unmatched,
        unmatched_details=unmatched_details,
        skipped_non_audio=skipped_non_audio,
    )


async def set_source_local_file(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    display_path: str,
) -> SourceTrack | None:
    """Assign a browser-reported path to a source row (manual confirmation after scan).

    Raises:
        ValueError: Empty or non-audio path.
    Returns:
        None if the source track does not exist for this user.
    """
    raw = (display_path or "").strip()
    if not raw:
        raise ValueError("path is required")
    if not is_audio_display_path(raw):
        raise ValueError("path must be an audio file (supported extension)")
    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id == source_track_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None
    row.local_file_path = raw
    row.downloaded_at = datetime.now(timezone.utc)
    row.manual_dl = False
    return row


async def clear_source_local_file(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
) -> bool:
    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id == source_track_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        return False
    row.local_file_path = None
    row.downloaded_at = None
    return True


async def set_source_manual_dl(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    manual_dl: bool,
) -> SourceTrack | None:
    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id == source_track_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None
    row.manual_dl = manual_dl
    return row
