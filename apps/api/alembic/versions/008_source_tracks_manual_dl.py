"""Add manual_dl flag on source_tracks.

Revision ID: 008
Revises: 0ebdf3810e9a
Create Date: 2026-04-16

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "0ebdf3810e9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_tracks",
        sa.Column(
            "manual_dl",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("source_tracks", "manual_dl")
