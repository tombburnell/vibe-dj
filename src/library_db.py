"""SQLite database management for library tracks.

Manages a SQLite database of tracks with playlist tracking,
download status, rekordbox collection status, and Amazon links.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


@dataclass
class LibraryTrack:
    """Unified track entity stored in SQLite database."""

    # Core metadata
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None

    # Spotify source
    spotify_id: str | None = None
    spotify_url: str | None = None
    playlists: list[str] = field(default_factory=list)

    # Rekordbox source
    in_rekordbox: bool = False
    rekordbox_file_path: str | None = None
    rekordbox_bpm: float | None = None
    rekordbox_genre: str | None = None
    rekordbox_key: str | None = None
    rekordbox_match_confidence: float | None = None  # 0.0-1.0

    # Purchase links
    amazon_url: str | None = None
    amazon_search_url: str | None = None
    amazon_price: str | None = None
    amazon_last_searched: str | None = None

    # Download status
    downloaded: bool = False
    download_path: str | None = None
    download_date: str | None = None

    # System fields
    last_updated: str | None = None
    id: str | None = None  # Generated: spotify_{spotify_id} or MD5 hash

    def __post_init__(self) -> None:
        """Generate ID and timestamp if not provided."""
        if self.id is None:
            self.id = self._generate_id()
        if self.last_updated is None:
            self.last_updated = datetime.now(timezone.utc).isoformat()

    def _generate_id(self) -> str:
        """Generate unique ID for track."""
        # Use spotify_id if available, otherwise hash artist + title
        if self.spotify_id:
            return f"spotify_{self.spotify_id}"
        else:
            key = f"{self.artist}|{self.title}".lower()
            return hashlib.md5(key.encode()).hexdigest()[:16]

    def normalize_artist(self) -> str:
        """Normalize artist name for comparison."""
        return self.artist.strip().lower()

    def normalize_title(self) -> str:
        """Normalize title for comparison."""
        return self.title.strip().lower()


class LibraryDB:
    """Manages SQLite database for library tracks."""

    def __init__(self, db_path: Path | str = "music.db") -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None
        self._connect()
        self._create_schema()

    def _connect(self) -> None:
        """Create SQLite connection."""
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow concurrent reads
        )
        self.conn.row_factory = sqlite3.Row  # Return rows as dict-like objects

    def _create_schema(self) -> None:
        """Create database tables and indexes if they don't exist."""
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()

        # Create tracks table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT,
                duration_ms INTEGER,
                
                -- Spotify source
                spotify_id TEXT,
                spotify_url TEXT,
                playlists TEXT,  -- JSON array stored as text
                
                -- Rekordbox source
                in_rekordbox BOOLEAN DEFAULT 0,
                rekordbox_file_path TEXT,
                rekordbox_bpm REAL,
                rekordbox_genre TEXT,
                rekordbox_key TEXT,
                rekordbox_match_confidence REAL,
                
                -- Purchase links
                amazon_url TEXT,
                amazon_search_url TEXT,
                amazon_price TEXT,
                amazon_last_searched TEXT,
                
                -- Download status
                downloaded BOOLEAN DEFAULT 0,
                download_path TEXT,
                download_date TEXT,
                
                -- System fields
                last_updated TEXT NOT NULL
            )
            """
        )

        # Create playlists table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                name TEXT PRIMARY KEY,
                source TEXT,
                csv_file TEXT,
                last_imported TEXT
            )
            """
        )

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_tracks_spotify_id ON tracks(spotify_id)",
            "CREATE INDEX IF NOT EXISTS idx_tracks_in_rekordbox ON tracks(in_rekordbox)",
            "CREATE INDEX IF NOT EXISTS idx_tracks_downloaded ON tracks(downloaded)",
            "CREATE INDEX IF NOT EXISTS idx_tracks_amazon_url ON tracks(amazon_url) WHERE amazon_url IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_tracks_rekordbox_file_path ON tracks(rekordbox_file_path) WHERE rekordbox_file_path IS NOT NULL",
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        self.conn.commit()

    def _row_to_track(self, row: sqlite3.Row) -> LibraryTrack:
        """Convert database row to LibraryTrack object."""
        # Parse playlists JSON array
        playlists: list[str] = []
        if row["playlists"]:
            try:
                playlists = json.loads(row["playlists"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse playlists JSON for track {row['id']}")

        return LibraryTrack(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            album=row["album"],
            duration_ms=row["duration_ms"],
            spotify_id=row["spotify_id"],
            spotify_url=row["spotify_url"],
            playlists=playlists,
            in_rekordbox=bool(row["in_rekordbox"]),
            rekordbox_file_path=row["rekordbox_file_path"],
            rekordbox_bpm=row["rekordbox_bpm"],
            rekordbox_genre=row["rekordbox_genre"],
            rekordbox_key=row["rekordbox_key"],
            rekordbox_match_confidence=row["rekordbox_match_confidence"],
            amazon_url=row["amazon_url"],
            amazon_search_url=row["amazon_search_url"],
            amazon_price=row["amazon_price"],
            amazon_last_searched=row["amazon_last_searched"],
            downloaded=bool(row["downloaded"]),
            download_path=row["download_path"],
            download_date=row["download_date"],
            last_updated=row["last_updated"],
        )

    def add_track(self, track: LibraryTrack) -> str:
        """Insert or update track (UPSERT).

        Args:
            track: Track to add or update

        Returns:
            Track ID
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        # Ensure ID and timestamp are set
        if track.id is None:
            track.id = track._generate_id()
        track.last_updated = datetime.now(timezone.utc).isoformat()

        # Serialize playlists as JSON
        playlists_json = json.dumps(track.playlists) if track.playlists else None

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO tracks (
                id, title, artist, album, duration_ms,
                spotify_id, spotify_url, playlists,
                in_rekordbox, rekordbox_file_path, rekordbox_bpm,
                rekordbox_genre, rekordbox_key, rekordbox_match_confidence,
                amazon_url, amazon_search_url, amazon_price, amazon_last_searched,
                downloaded, download_path, download_date,
                last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                artist = excluded.artist,
                album = excluded.album,
                duration_ms = excluded.duration_ms,
                spotify_id = excluded.spotify_id,
                spotify_url = excluded.spotify_url,
                playlists = excluded.playlists,
                in_rekordbox = excluded.in_rekordbox,
                rekordbox_file_path = excluded.rekordbox_file_path,
                rekordbox_bpm = excluded.rekordbox_bpm,
                rekordbox_genre = excluded.rekordbox_genre,
                rekordbox_key = excluded.rekordbox_key,
                rekordbox_match_confidence = excluded.rekordbox_match_confidence,
                amazon_url = excluded.amazon_url,
                amazon_search_url = excluded.amazon_search_url,
                amazon_price = excluded.amazon_price,
                amazon_last_searched = excluded.amazon_last_searched,
                downloaded = excluded.downloaded,
                download_path = excluded.download_path,
                download_date = excluded.download_date,
                last_updated = excluded.last_updated
            """,
            (
                track.id,
                track.title,
                track.artist,
                track.album,
                track.duration_ms,
                track.spotify_id,
                track.spotify_url,
                playlists_json,
                track.in_rekordbox,
                track.rekordbox_file_path,
                track.rekordbox_bpm,
                track.rekordbox_genre,
                track.rekordbox_key,
                track.rekordbox_match_confidence,
                track.amazon_url,
                track.amazon_search_url,
                track.amazon_price,
                track.amazon_last_searched,
                track.downloaded,
                track.download_path,
                track.download_date,
                track.last_updated,
            ),
        )

        return track.id

    def get_track(self, track_id: str) -> LibraryTrack | None:
        """Get track by ID.

        Args:
            track_id: Track ID

        Returns:
            LibraryTrack if found, None otherwise
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_track(row)

    def find_track(
        self, title: str, artist: str, threshold: float = 85.0
    ) -> tuple[LibraryTrack | None, float]:
        """Find matching track using fuzzy matching.

        Args:
            title: Track title
            artist: Track artist
            threshold: Minimum match score (0-100)

        Returns:
            Tuple of (found track, match score) or (None, 0.0)
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        # Get all tracks for fuzzy matching
        all_tracks = self.get_all_tracks()

        # Normalize search strings
        search_string = f"{artist.strip().lower()} {title.strip().lower()}"

        best_match: LibraryTrack | None = None
        best_score = 0.0

        for db_track in all_tracks:
            db_string = f"{db_track.normalize_artist()} {db_track.normalize_title()}"
            score = fuzz.token_sort_ratio(search_string, db_string)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = db_track

        if best_match:
            return (best_match, best_score)
        return (None, 0.0)

    def update_track(self, track_id: str, updates: dict[str, Any]) -> None:
        """Update specific fields of a track.

        Args:
            track_id: Track ID
            updates: Dictionary of field names to values
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        # Handle playlists specially (convert to JSON)
        if "playlists" in updates and isinstance(updates["playlists"], list):
            updates["playlists"] = json.dumps(updates["playlists"])

        # Always update last_updated
        updates["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Build UPDATE statement
        set_clauses = [f"{key} = ?" for key in updates.keys()]
        values = list(updates.values()) + [track_id]

        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE tracks SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )

    def get_all_tracks(self) -> list[LibraryTrack]:
        """Get all tracks from database.

        Returns:
            List of LibraryTrack objects
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracks")
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def get_tracks_without_amazon_links(self) -> list[LibraryTrack]:
        """Get tracks without Amazon links.

        Returns:
            List of LibraryTrack objects
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE amazon_url IS NULL")
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def get_missing_tracks(self) -> list[LibraryTrack]:
        """Get tracks that are not downloaded and not in Rekordbox.

        Returns:
            List of LibraryTrack objects
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM tracks WHERE downloaded = 0 AND in_rekordbox = 0"
        )
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def get_tracks_in_rekordbox(self) -> list[LibraryTrack]:
        """Get tracks that are in Rekordbox.

        Returns:
            List of LibraryTrack objects
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE in_rekordbox = 1")
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def get_undownloaded_tracks_without_rekordbox(self) -> list[LibraryTrack]:
        """Get tracks that are not downloaded and don't have Rekordbox file paths.

        Returns:
            List of LibraryTrack objects
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM tracks WHERE downloaded = 0 AND rekordbox_file_path IS NULL"
        )
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def get_tracks_by_playlist(self, playlist_name: str) -> list[LibraryTrack]:
        """Get tracks by playlist name.

        Args:
            playlist_name: Name of playlist

        Returns:
            List of LibraryTrack objects
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()
        # Use JSON functions to filter by playlist name
        cursor.execute(
            """
            SELECT * FROM tracks
            WHERE json_extract(playlists, '$') IS NOT NULL
            AND json_extract(playlists, '$') LIKE ?
            """,
            (f'%"{playlist_name}"%',),
        )
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def commit(self) -> None:
        """Commit current transaction."""
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")
        self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> LibraryDB:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
