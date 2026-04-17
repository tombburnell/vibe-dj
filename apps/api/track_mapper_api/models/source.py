from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from track_mapper_api.models.base import Base
from track_mapper_api.models.playlist import source_track_playlists


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceTrack(Base):
    __tablename__ = "source_tracks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    artist: Mapped[str] = mapped_column(Text, nullable=False)
    album: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spotify_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    spotify_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_wishlist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    local_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_dl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    amazon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    amazon_search_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    amazon_price: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amazon_link_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    amazon_link_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    amazon_last_searched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    amazon_candidates_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    playlists: Mapped[list["Playlist"]] = relationship(
        secondary=source_track_playlists, back_populates="source_tracks"
    )
