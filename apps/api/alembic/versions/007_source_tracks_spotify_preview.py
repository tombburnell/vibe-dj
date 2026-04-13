"""Add Spotify preview URL and no-preview flag on source_tracks.

Revision ID: 007
Revises: 006
Create Date: 2026-04-13

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_tracks",
        sa.Column("spotify_preview_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_tracks",
        sa.Column(
            "no_spotify_preview",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("source_tracks", "no_spotify_preview")
    op.drop_column("source_tracks", "spotify_preview_url")
