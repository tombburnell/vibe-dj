"""Add spotify_playlist_url to playlists.

Revision ID: 0ebdf3810e9a
Revises: 007
Create Date: 2026-04-15 14:30:46.152022

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0ebdf3810e9a"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column("spotify_playlist_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("playlists", "spotify_playlist_url")
