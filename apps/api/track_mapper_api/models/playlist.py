from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from track_mapper_api.models.base import Base

if TYPE_CHECKING:
    from track_mapper_api.models.source import SourceTrack


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


source_track_playlists = Table(
    "source_track_playlists",
    Base.metadata,
    Column(
        "source_track_id",
        Uuid(as_uuid=True),
        ForeignKey("source_tracks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "playlist_id",
        Uuid(as_uuid=True),
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    import_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Spotify catalog id when imported via Web API; used to merge re-imports.
    spotify_playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    source_tracks: Mapped[list["SourceTrack"]] = relationship(
        secondary=source_track_playlists, back_populates="playlists"
    )
