"""rekordbox collection parser.

Supports reading rekordbox XML exports and database files using pyrekordbox.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

try:
    from pyrekordbox import RekordboxCollection
except ImportError:
    RekordboxCollection = None  # type: ignore


@dataclass
class RekordboxTrack:
    """Represents a track from rekordbox collection."""

    title: str
    artist: str
    album: str | None = None
    file_path: str | None = None
    duration_ms: int | None = None
    bpm: float | None = None
    key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert track to dictionary."""
        return asdict(self)

    def normalize_artist(self) -> str:
        """Normalize artist name for comparison."""
        return self.artist.strip().lower()

    def normalize_title(self) -> str:
        """Normalize title for comparison."""
        return self.title.strip().lower()


class RekordboxParser:
    """Parse rekordbox collection files."""

    def __init__(self) -> None:
        """Initialize the parser."""
        pass

    def parse_xml(self, xml_path: Path | str) -> list[RekordboxTrack]:
        """Parse rekordbox XML export file.

        Args:
            xml_path: Path to rekordbox XML file

        Returns:
            List of RekordboxTrack objects
        """
        xml_path = Path(xml_path)
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        tracks: list[RekordboxTrack] = []

        # rekordbox XML structure: DJ_PLAYLISTS -> COLLECTION -> TRACK
        for collection in root.findall(".//COLLECTION"):
            for track_elem in collection.findall("TRACK"):
                track = self._parse_xml_track(track_elem)
                if track:
                    tracks.append(track)

        return tracks

    def _parse_xml_track(self, track_elem: ET.Element) -> RekordboxTrack | None:
        """Parse a single track element from XML.

        Args:
            track_elem: XML element representing a track

        Returns:
            RekordboxTrack object or None if parsing fails
        """
        # Extract track attributes
        title = track_elem.get("Name", "").strip()
        artist = track_elem.get("Artist", "").strip()
        album = track_elem.get("Album", "").strip() or None

        # File path
        location = track_elem.get("Location", "")
        # rekordbox uses file:// URLs, decode if needed
        if location.startswith("file://"):
            file_path = location.replace("file://", "")
            # Decode URL encoding
            import urllib.parse

            file_path = urllib.parse.unquote(file_path)
        else:
            file_path = location if location else None

        # Duration (in seconds, convert to ms)
        total_time = track_elem.get("TotalTime", "")
        duration_ms = None
        if total_time:
            try:
                duration_ms = int(float(total_time) * 1000)
            except ValueError:
                pass

        # BPM
        bpm = None
        bpm_str = track_elem.get("AverageBpm", "")
        if bpm_str:
            try:
                bpm = float(bpm_str)
            except ValueError:
                pass

        # Key
        key = track_elem.get("Tonality", "") or None

        if not title and not artist:
            return None

        return RekordboxTrack(
            title=title or "Unknown Title",
            artist=artist or "Unknown Artist",
            album=album,
            file_path=file_path,
            duration_ms=duration_ms,
            bpm=bpm,
            key=key,
        )

    def parse_database(
        self, db_path: Path | str | None = None
    ) -> list[RekordboxTrack]:
        """Parse rekordbox database file using pyrekordbox.

        Args:
            db_path: Path to rekordbox database file (optional, uses default if None)

        Returns:
            List of RekordboxTrack objects
        """
        if RekordboxCollection is None:
            raise ImportError(
                "pyrekordbox is not installed. Install it with: uv add pyrekordbox"
            )

        try:
            if db_path:
                collection = RekordboxCollection(db_path)
            else:
                # Try to find default rekordbox database location
                collection = RekordboxCollection()
        except Exception as e:
            raise RuntimeError(f"Failed to open rekordbox database: {e}") from e

        tracks: list[RekordboxTrack] = []

        try:
            # Iterate through tracks in collection
            for track_data in collection.tracks():
                track = self._parse_database_track(track_data)
                if track:
                    tracks.append(track)
        except Exception as e:
            raise RuntimeError(f"Failed to parse rekordbox database: {e}") from e

        return tracks

    def _parse_database_track(self, track_data: Any) -> RekordboxTrack | None:
        """Parse a track from rekordbox database.

        Args:
            track_data: Track data from pyrekordbox

        Returns:
            RekordboxTrack object or None if parsing fails
        """
        try:
            # Extract fields from track data
            title = getattr(track_data, "title", None) or getattr(
                track_data, "name", None
            ) or ""
            artist = getattr(track_data, "artist", None) or ""
            album = getattr(track_data, "album", None) or None
            file_path = getattr(track_data, "file_path", None) or getattr(
                track_data, "location", None
            ) or None

            # Duration
            duration_ms = None
            if hasattr(track_data, "duration_ms"):
                duration_ms = track_data.duration_ms
            elif hasattr(track_data, "duration"):
                duration = track_data.duration
                if isinstance(duration, (int, float)):
                    duration_ms = int(duration * 1000) if duration < 1000 else int(
                        duration
                    )

            # BPM
            bpm = getattr(track_data, "bpm", None) or getattr(
                track_data, "average_bpm", None
            ) or None

            # Key
            key = getattr(track_data, "key", None) or getattr(
                track_data, "tonality", None
            ) or None

            if not title and not artist:
                return None

            return RekordboxTrack(
                title=str(title).strip() or "Unknown Title",
                artist=str(artist).strip() or "Unknown Artist",
                album=str(album).strip() if album else None,
                file_path=str(file_path) if file_path else None,
                duration_ms=duration_ms,
                bpm=float(bpm) if bpm else None,
                key=str(key) if key else None,
            )
        except Exception as e:
            print(f"Warning: Failed to parse track: {e}")
            return None

    def export_to_json(self, tracks: list[RekordboxTrack], output_path: Path | str) -> None:
        """Export tracks to JSON file.

        Args:
            tracks: List of RekordboxTrack objects
            output_path: Path to output JSON file
        """
        output_path = Path(output_path)
        data = [track.to_dict() for track in tracks]
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(tracks)} tracks to {output_path}")


def main() -> None:
    """Example usage."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python rekordbox_parser.py <xml_file> [db_path]")
        print("  xml_file: Path to rekordbox XML export")
        print("  db_path: Optional path to rekordbox database")
        sys.exit(1)

    parser = RekordboxParser()

    xml_path = sys.argv[1]
    print(f"Parsing rekordbox XML: {xml_path}")
    tracks = parser.parse_xml(xml_path)

    print(f"\nFound {len(tracks)} tracks:")
    for i, track in enumerate(tracks[:10], 1):  # Show first 10
        print(f"{i}. {track.artist} - {track.title}")

    if len(tracks) > 10:
        print(f"... and {len(tracks) - 10} more")

    # Export to JSON
    output_file = Path("rekordbox_collection.json")
    parser.export_to_json(tracks, output_file)


if __name__ == "__main__":
    main()

