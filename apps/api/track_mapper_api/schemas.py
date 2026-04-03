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
