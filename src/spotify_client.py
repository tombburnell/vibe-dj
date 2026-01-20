"""Spotify playlist extractor from CSV files.

Supports reading playlists exported from chosic.com or other CSV exporters.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class Track:
    """Represents a track with normalized metadata."""

    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    spotify_id: str | None = None
    spotify_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert track to dictionary."""
        return asdict(self)

    def normalize_artist(self) -> str:
        """Normalize artist name for comparison."""
        return self.artist.strip().lower()

    def normalize_title(self) -> str:
        """Normalize title for comparison."""
        return self.title.strip().lower()


class SpotifyPlaylistExtractor:
    """Extract tracks from Spotify playlist CSV files."""

    def __init__(self) -> None:
        """Initialize the extractor."""
        pass

    def parse_csv(self, csv_path: Path | str) -> list[Track]:
        """Parse a CSV file exported from chosic.com or similar.

        Args:
            csv_path: Path to CSV file

        Returns:
            List of Track objects
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        print(f"[DEBUG] Reading CSV file: {csv_path}")

        tracks: list[Track] = []

        with csv_path.open("r", encoding="utf-8") as f:
            # Try to detect delimiter
            sample = f.read(1024)
            f.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter

            reader = csv.DictReader(f, delimiter=delimiter)

            for i, row in enumerate(reader, 1):
                try:
                    track = self._parse_csv_row(row)
                    if track:
                        tracks.append(track)
                        if i <= 5:  # Show first 5 for debugging
                            print(f"[DEBUG] Track {i}: {track.artist} - {track.title}")
                except Exception as e:
                    print(f"[WARNING] Failed to parse row {i}: {e}")
                    continue

        print(f"[DEBUG] Successfully parsed {len(tracks)} tracks from CSV")
        return tracks

    def _parse_csv_row(self, row: dict[str, str]) -> Track | None:
        """Parse a CSV row into a Track object.

        Args:
            row: Dictionary representing a CSV row

        Returns:
            Track object or None if parsing fails
        """
        # Handle different column name variations
        title = (
            row.get("Song")
            or row.get("song")
            or row.get("Title")
            or row.get("title")
            or row.get("Track Name")
            or row.get("track_name")
            or ""
        ).strip()

        artist = (
            row.get("Artist")
            or row.get("artist")
            or row.get("Artist Name")
            or row.get("artist_name")
            or ""
        ).strip()

        album = (
            row.get("Album")
            or row.get("album")
            or row.get("Album Name")
            or row.get("album_name")
            or None
        )
        if album:
            album = album.strip() or None

        # Parse duration (could be MM:SS or seconds)
        duration_ms = None
        duration_str = (
            row.get("Duration")
            or row.get("duration")
            or row.get("Track Duration")
            or row.get("track_duration")
            or ""
        ).strip()

        if duration_str:
            duration_ms = self._parse_duration(duration_str)

        # Extract Spotify ID and build URL
        spotify_id = (
            row.get("Spotify Track Id")
            or row.get("spotify_track_id")
            or row.get("Track ID")
            or row.get("track_id")
            or row.get("id")
            or None
        )
        if spotify_id:
            spotify_id = spotify_id.strip()
            spotify_url = f"https://open.spotify.com/track/{spotify_id}"
        else:
            spotify_url = None

        if not title or not artist:
            return None

        return Track(
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            spotify_id=spotify_id,
            spotify_url=spotify_url,
        )

    def _parse_duration(self, duration_str: str) -> int | None:
        """Parse duration string to milliseconds.

        Handles formats like:
        - "05:39" (MM:SS)
        - "339" (seconds)
        - "5:39" (M:SS)

        Args:
            duration_str: Duration string

        Returns:
            Duration in milliseconds or None if parsing fails
        """
        try:
            # Try MM:SS format
            if ":" in duration_str:
                parts = duration_str.split(":")
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    return (minutes * 60 + seconds) * 1000
            else:
                # Assume seconds
                seconds = int(float(duration_str))
                return seconds * 1000
        except (ValueError, TypeError):
            return None

    def export_to_json(self, tracks: list[Track], output_path: Path | str) -> None:
        """Export tracks to JSON file.

        Args:
            tracks: List of Track objects
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
        print("Usage: python spotify_client.py <csv_file>")
        print("\nExample:")
        print("  python spotify_client.py playlists/koko-groove.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    extractor = SpotifyPlaylistExtractor()

    print(f"Extracting tracks from CSV: {csv_file}")
    try:
        tracks = extractor.parse_csv(csv_file)
        print(f"\nFound {len(tracks)} tracks:")
        for i, track in enumerate(tracks, 1):
            print(f"{i}. {track.artist} - {track.title}")

        # Export to JSON
        csv_path = Path(csv_file)
        output_file = csv_path.parent / f"{csv_path.stem}.json"
        extractor.export_to_json(tracks, output_file)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
