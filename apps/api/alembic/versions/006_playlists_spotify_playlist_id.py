"""Add spotify_playlist_id to playlists for import deduplication.

Revision ID: 006
Revises: 005
Create Date: 2026-04-06

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column("spotify_playlist_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_playlists_user_spotify_playlist",
        "playlists",
        ["user_id", "spotify_playlist_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_playlists_user_spotify_playlist", table_name="playlists")
    op.drop_column("playlists", "spotify_playlist_id")
