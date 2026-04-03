"""Initial Postgres schema (track mapper).

Revision ID: 001
Revises:
Create Date: 2026-04-03

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_library_snapshots_user_id", "library_snapshots", ["user_id"])

    op.create_table(
        "library_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("library_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("artist", sa.Text(), nullable=False),
        sa.Column("album", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("bpm", sa.Float(), nullable=True),
        sa.Column("musical_key", sa.String(length=32), nullable=True),
        sa.Column("genre", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["library_snapshot_id"], ["library_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_library_tracks_user_id", "library_tracks", ["user_id"])
    op.create_index(
        "ix_library_tracks_user_snapshot", "library_tracks", ["user_id", "library_snapshot_id"]
    )

    op.create_table(
        "playlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("import_source", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_playlists_user_id", "playlists", ["user_id"])

    op.create_table(
        "source_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("artist", sa.Text(), nullable=False),
        sa.Column("album", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("spotify_id", sa.String(length=64), nullable=True),
        sa.Column("spotify_url", sa.Text(), nullable=True),
        sa.Column("on_wishlist", sa.Boolean(), nullable=False),
        sa.Column("local_file_path", sa.Text(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amazon_url", sa.Text(), nullable=True),
        sa.Column("amazon_search_url", sa.Text(), nullable=True),
        sa.Column("amazon_price", sa.String(length=32), nullable=True),
        sa.Column("amazon_last_searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_tracks_user_id", "source_tracks", ["user_id"])
    op.create_index("ix_source_tracks_spotify_id", "source_tracks", ["spotify_id"])
    op.create_index(
        "uq_source_track_spotify",
        "source_tracks",
        ["user_id", "spotify_id"],
        unique=True,
        postgresql_where=sa.text("spotify_id IS NOT NULL"),
    )

    op.create_table(
        "source_track_playlists",
        sa.Column("source_track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playlist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_track_id"], ["source_tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_track_id", "playlist_id"),
    )

    op.create_table(
        "source_library_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("source_track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("library_track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("library_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("rejected_through_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(length=128), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("match_debug", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["library_snapshot_id"], ["library_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["library_track_id"], ["library_tracks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rejected_through_snapshot_id"], ["library_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_track_id"], ["source_tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_library_links_user_id", "source_library_links", ["user_id"])
    op.create_index(
        "uq_source_active_link",
        "source_library_links",
        ["user_id", "source_track_id", "library_snapshot_id"],
        unique=True,
        postgresql_where=sa.text("decision IN ('auto', 'confirmed', 'picked')"),
    )


def downgrade() -> None:
    op.drop_index("uq_source_active_link", table_name="source_library_links")
    op.drop_index("ix_source_library_links_user_id", table_name="source_library_links")
    op.drop_table("source_library_links")
    op.drop_table("source_track_playlists")
    op.drop_index("uq_source_track_spotify", table_name="source_tracks")
    op.drop_index("ix_source_tracks_spotify_id", table_name="source_tracks")
    op.drop_index("ix_source_tracks_user_id", table_name="source_tracks")
    op.drop_table("source_tracks")
    op.drop_index("ix_playlists_user_id", table_name="playlists")
    op.drop_table("playlists")
    op.drop_index("ix_library_tracks_user_snapshot", table_name="library_tracks")
    op.drop_index("ix_library_tracks_user_id", table_name="library_tracks")
    op.drop_table("library_tracks")
    op.drop_index("ix_library_snapshots_user_id", table_name="library_snapshots")
    op.drop_table("library_snapshots")
