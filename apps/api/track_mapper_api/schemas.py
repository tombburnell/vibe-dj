"""Pydantic schemas aligned with docs/data-model.md (subset for list endpoints)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

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
    top_match_below_minimum: bool = False


class SourceTopMatchesRequest(BaseModel):
    source_track_ids: list[str] = Field(default_factory=list, max_length=100)
    min_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum fuzzy score for top match; picked rows ignore this floor.",
    )


class AmazonLinkCandidateOut(BaseModel):
    url: str
    title: str | None = None
    artist: str | None = None
    match_score: float | None = None
    price: str | None = None
    broken: bool = False


class MarkLinkBrokenIn(BaseModel):
    url: str = Field(..., min_length=1, max_length=4096)


class FindAmazonLinksRequest(BaseModel):
    source_track_ids: list[str] = Field(default_factory=list, max_length=200)
    force: bool = False
    #: Override env for this request: Serper (Google) vs ``ddgs`` (Brave by default).
    web_search_provider: Literal["serper", "ddg"] | None = None


class FindAmazonLinksOut(BaseModel):
    searched_count: int
    skipped_not_need_count: int
    skipped_cached_count: int
    error_count: int


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
    playlist_ids: list[str] = Field(
        default_factory=list,
        description="Playlist row UUIDs for this source (same order as playlist_names).",
    )
    local_file_path: str | None = None
    downloaded_at: datetime | None = None
    amazon_url: str | None = None
    amazon_search_url: str | None = None
    amazon_price: str | None = None
    amazon_link_title: str | None = None
    amazon_link_match_score: float | None = None
    amazon_last_searched_at: datetime | None = None
    amazon_candidates: list[AmazonLinkCandidateOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    # Best fuzzy match vs latest library snapshot (null if no snapshot / no candidates).
    top_match_title: str | None = None
    top_match_artist: str | None = None
    top_match_score: float | None = None
    top_match_duration_ms: int | None = None
    top_match_library_track_id: str | None = None
    top_match_is_picked: bool = False
    is_rejected_no_match: bool = False
    top_match_below_minimum: bool = False


class SourceWishlistBatchIn(BaseModel):
    source_track_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    on_wishlist: bool


class SourceWishlistBatchOut(BaseModel):
    ok: bool = True
    updated_count: int


class LocalScanFileIn(BaseModel):
    path: str = Field(..., min_length=1, max_length=2048)


class LocalScanRequest(BaseModel):
    files: list[LocalScanFileIn] = Field(..., max_length=5000)
    min_score: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Minimum rapidfuzz token_sort_ratio (0–100); mirrors legacy download_scanner default.",
    )


class LocalScanMatchedOut(BaseModel):
    source_track_id: str
    path: str
    score: float
    title: str
    artist: str


class LocalScanUnmatchedOut(BaseModel):
    path: str
    parsed_artist: str | None = None
    parsed_title: str | None = None
    best_score: float
    best_source_track_id: str | None = None
    best_source_artist: str | None = None
    best_source_title: str | None = None
    below_threshold: bool
    source_claimed_by_other_file: bool
    best_source_already_has_file: bool = False


class LocalScanOut(BaseModel):
    matched: list[LocalScanMatchedOut]
    unmatched_files: list[str]
    unmatched_details: list[LocalScanUnmatchedOut]
    skipped_non_audio: int
    min_score: float


class ClearLocalFileOut(BaseModel):
    cleared: bool


class SetLocalFileIn(BaseModel):
    path: str = Field(..., min_length=1, max_length=2048)


class SetLocalFileOut(BaseModel):
    source_track_id: str
    path: str
    title: str
    artist: str


class LibrarySnapshotImportOut(BaseModel):
    snapshot_id: str
    track_count: int


class PlaylistImportOut(BaseModel):
    playlist_id: str
    rows_linked: int
    new_source_tracks: int


class SpotifyPlaylistImportIn(BaseModel):
    playlist_id_or_url: str = Field(..., min_length=1, max_length=2048)
    playlist_name: str | None = Field(None, max_length=512)


class SpotifyOAuthTokenIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=4096)
    code_verifier: str = Field(..., min_length=43, max_length=128)
    redirect_uri: str = Field(..., min_length=1, max_length=2048)


class SpotifyOAuthTokenOut(BaseModel):
    ok: bool = True


class SpotifyOAuthStatusOut(BaseModel):
    connected: bool
    spotify_user_id: str | None = None


class SpotifyOAuthConfigOut(BaseModel):
    client_id: str
    redirect_uri: str


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
    title_match_score: float
    artist_match_score: float
