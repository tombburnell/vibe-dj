"""Best Amazon link title and match score on source_tracks.

Revision ID: 004
Revises: 003
Create Date: 2026-04-04

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_tracks", sa.Column("amazon_link_title", sa.Text(), nullable=True))
    op.add_column(
        "source_tracks",
        sa.Column("amazon_link_match_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_tracks", "amazon_link_match_score")
    op.drop_column("source_tracks", "amazon_link_title")
