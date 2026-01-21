"""Parse Rekordbox TSV export files.

Extracts track metadata from tab-separated Rekordbox export files and creates
normalized track objects for matching.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .track_normalizer import (
    create_all_tokens,
    create_base_title,
    extract_artist_tokens,
    normalize_text,
)

logger = logging.getLogger(__name__)


@dataclass
class RekordboxTSVTrack:
    """Rekordbox track from TSV export with normalized fields."""

    # Raw fields from TSV
    title: str
    artist: str
    album: str | None = None
    genre: str | None = None
    bpm: float | None = None
    key: str | None = None
    duration_ms: int | None = None
    file_path: str = ""

    # Normalized/computed fields (populated after normalization)
    base_title: str = field(default="", init=False)
    full_title: str = field(default="", init=False)
    artist_tokens: list[str] = field(default_factory=list, init=False)
    all_tokens: list[str] = field(default_factory=list, init=False)

    # Internal ID for indexing
    rb_track_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        """Populate normalized fields and generate ID."""
        # Normalize fields
        self.full_title = normalize_text(self.title)
        self.base_title = create_base_title(self.title)
        self.artist_tokens = extract_artist_tokens(self.artist)
        self.all_tokens = create_all_tokens(self.title, self.artist)

        # Generate ID (use file_path if available, otherwise hash title+artist)
        if self.file_path:
            key = self.file_path.lower()
        else:
            key = f"{self.artist}|{self.title}".lower()
        self.rb_track_id = hashlib.md5(key.encode()).hexdigest()[:16]


def parse_time_to_ms(time_str: str) -> int | None:
    """Convert MM:SS to milliseconds.

    Args:
        time_str: Time string in MM:SS format

    Returns:
        Duration in milliseconds or None if invalid
    """
    if not time_str or not time_str.strip():
        return None

    try:
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return None
        minutes = int(parts[0])
        seconds = int(parts[1])
        total_seconds = minutes * 60 + seconds
        return total_seconds * 1000
    except (ValueError, IndexError):
        return None


class RekordboxTSVParser:
    """Parse Rekordbox TSV export files."""

    def parse_tsv(self, tsv_path: Path | str) -> list[RekordboxTSVTrack]:
        """Parse tab-separated Rekordbox export file.

        Args:
            tsv_path: Path to TSV file

        Returns:
            List of RekordboxTSVTrack objects
        """
        tsv_path = Path(tsv_path)
        if not tsv_path.exists():
            raise FileNotFoundError(f"TSV file not found: {tsv_path}")

        tracks: list[RekordboxTSVTrack] = []
        skipped_rows = 0

        # Try different encodings (including UTF-16 variants)
        encodings = ["utf-16-le", "utf-16-be", "utf-8-sig", "utf-8", "latin-1", "cp1252"]
        file_handle = None
        encoding_used = None

        for encoding in encodings:
            try:
                # Read first few bytes to test encoding
                with tsv_path.open("rb") as test_file:
                    test_file.read(1000)
                file_handle = tsv_path.open("r", encoding=encoding)
                # Try reading first line to verify
                first_line = file_handle.readline()
                file_handle.seek(0)  # Reset to beginning
                encoding_used = encoding
                break
            except (UnicodeDecodeError, UnicodeError):
                if file_handle:
                    file_handle.close()
                file_handle = None
                continue

        if file_handle is None:
            # Last resort: try with errors='ignore'
            file_handle = tsv_path.open("r", encoding="utf-8", errors="replace")
            encoding_used = "utf-8 (with errors='replace')"

        if encoding_used and encoding_used != "utf-8":
            logger.info(f"Using encoding {encoding_used} for {tsv_path}")

        try:
            for line_num, line in enumerate(file_handle, start=1):
                # Skip header row (starts with # or contains "Track Title")
                if line_num == 1:
                    if line.strip().startswith("#") or "Track Title" in line:
                        continue

                # Skip empty lines
                if not line.strip():
                    continue

                # Parse row
                track = self._parse_row(line, line_num)
                if track:
                    tracks.append(track)
                else:
                    skipped_rows += 1
        finally:
            file_handle.close()

        if skipped_rows > 0:
            logger.warning(f"Skipped {skipped_rows} invalid rows from {tsv_path}")

        logger.info(f"Parsed {len(tracks)} tracks from {tsv_path}")
        return tracks

    def _parse_row(self, line: str, line_num: int) -> RekordboxTSVTrack | None:
        """Parse a single TSV row.

        Args:
            line: Tab-separated line
            line_num: Line number for error reporting

        Returns:
            RekordboxTSVTrack or None if invalid
        """
        try:
            columns = line.strip().split("\t")

            # Need at least 16 columns (0-15)
            if len(columns) < 16:
                logger.debug(f"Row {line_num}: insufficient columns ({len(columns)})")
                return None

            # Extract columns
            # Column mapping: 0=#, 1=DJ Play Count, 2=Rating, 3=BPM, 4=Key, 5=Time, 6=Color, 7=Track Title, 8=Artist, ...
            bpm_str = columns[3].strip() if len(columns) > 3 else ""
            key = columns[4].strip() if len(columns) > 4 else ""  # Key is at index 4
            time_str = columns[5].strip() if len(columns) > 5 else ""  # Time is at index 5
            title = columns[7].strip() if len(columns) > 7 else ""
            artist = columns[8].strip() if len(columns) > 8 else ""
            genre = columns[12].strip() if len(columns) > 12 else ""
            album = columns[13].strip() if len(columns) > 13 else ""
            file_path = columns[15].strip() if len(columns) > 15 else ""

            # Require at least title or artist
            if not title and not artist:
                logger.debug(f"Row {line_num}: missing title and artist")
                return None

            # Skip header-like rows
            if title == "Track Title" or artist == "Artist":
                return None

            # Parse BPM
            bpm: float | None = None
            if bpm_str:
                try:
                    bpm = float(bpm_str)
                except ValueError:
                    pass

            # Parse duration
            duration_ms = parse_time_to_ms(time_str)

            # Create track (normalized fields populated in __post_init__)
            track = RekordboxTSVTrack(
                title=title or "Unknown Title",
                artist=artist or "Unknown Artist",
                album=album if album else None,
                genre=genre if genre else None,
                bpm=bpm,
                key=key if key else None,
                duration_ms=duration_ms,
                file_path=file_path,
            )

            return track

        except Exception as e:
            logger.warning(f"Row {line_num}: parsing error: {e}")
            return None
