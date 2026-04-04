"""Pydantic schemas aligned with docs/data-model.md (subset for list endpoints)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LibraryTrackOut(BaseModel):
    id: str
    user_id: str
    library_snapshot_id: str
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    file_path: str
    bpm: float | None = None
    musical_key: str | None = None
    genre: str | None = None
    created_at: datetime


class LibraryTrackPageOut(BaseModel):
    items: list[LibraryTrackOut]
    next_cursor: str | None = None


class SourceTopMatchRowOut(BaseModel):
    """Per-row best match for batch overlay (same snapshot rules as list used to compute)."""

    source_track_id: str
    top_match_library_track_id: str | None = None
    top_match_title: str | None = None
    top_match_artist: str | None = None
    top_match_score: float | None = None
    top_match_duration_ms: int | None = None
    top_match_is_picked: bool = False
    is_rejected_no_match: bool = False


class SourceTopMatchesRequest(BaseModel):
    source_track_ids: list[str] = Field(default_factory=list, max_length=100)
    min_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum fuzzy score for top match; picked rows ignore this floor.",
    )


class SourceTrackOut(BaseModel):
    id: str
    user_id: str
    source_kind: str
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    spotify_id: str | None = None
    spotify_url: str | None = None
    on_wishlist: bool = True
    playlist_names: list[str] = Field(default_factory=list)
    local_file_path: str | None = None
    downloaded_at: datetime | None = None
    amazon_url: str | None = None
    amazon_search_url: str | None = None
    created_at: datetime
    updated_at: datetime
    # Best fuzzy match vs latest library snapshot (null if no snapshot / no candidates).
    top_match_title: str | None = None
    top_match_artist: str | None = None
    top_match_score: float | None = None
    top_match_duration_ms: int | None = None


class LibrarySnapshotImportOut(BaseModel):
    snapshot_id: str
    track_count: int


class PlaylistImportOut(BaseModel):
    playlist_id: str
    rows_linked: int
    new_source_tracks: int


class PlaylistOut(BaseModel):
    id: str
    name: str
    import_source: str | None = None
    created_at: datetime


class MatchRunOut(BaseModel):
    library_snapshot_id: str | None
    matched_count: int
    skipped_count: int


class LibraryCandidateOut(LibraryTrackOut):
    match_score: float
