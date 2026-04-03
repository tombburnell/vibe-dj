"""Index for keyset pagination on library_tracks.

Revision ID: 002
Revises: 001
Create Date: 2026-04-03

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_lt_user_snap_path_id",
        "library_tracks",
        ["user_id", "library_snapshot_id", "file_path", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lt_user_snap_path_id", table_name="library_tracks")
