from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from track_mapper_api.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SpotifyUserConnection(Base):
    """Stored OAuth tokens per Track Mapper user (dev header / future auth)."""

    __tablename__ = "spotify_user_connections"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spotify_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
