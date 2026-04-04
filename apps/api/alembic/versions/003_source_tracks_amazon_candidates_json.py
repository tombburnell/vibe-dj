"""Amazon link search candidates JSON on source_tracks.

Revision ID: 003
Revises: 002
Create Date: 2026-04-04

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_tracks",
        sa.Column("amazon_candidates_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_tracks", "amazon_candidates_json")
