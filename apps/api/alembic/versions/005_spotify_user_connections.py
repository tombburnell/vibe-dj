"""Spotify OAuth tokens per user for playlist import.

Revision ID: 005
Revises: 004
Create Date: 2026-04-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spotify_user_connections",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spotify_user_id", sa.String(length=128), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("spotify_user_connections")
