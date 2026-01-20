"""Track matching and comparison logic.

Uses fuzzy matching to compare Spotify tracks with rekordbox collection
and identify missing tracks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process

try:
    from rekordbox_parser import RekordboxTrack
    from spotify_client import Track
except ImportError:
    from .rekordbox_parser import RekordboxTrack
    from .spotify_client import Track


@dataclass
class MatchResult:
    """Result of track matching."""

    spotify_track: Track
    rekordbox_track: RekordboxTrack | None
    match_score: float
    is_match: bool


class TrackMatcher:
    """Match Spotify tracks with rekordbox collection."""

    def __init__(self, threshold: float = 85.0) -> None:
        """Initialize the matcher.

        Args:
            threshold: Minimum fuzzy match score (0-100) to consider a match
        """
        self.threshold = threshold

    def find_missing_tracks(
        self, spotify_tracks: list[Track], rekordbox_tracks: list[RekordboxTrack]
    ) -> list[Track]:
        """Find tracks in Spotify playlist that are missing from rekordbox.

        Args:
            spotify_tracks: List of tracks from Spotify playlist
            rekordbox_tracks: List of tracks from rekordbox collection

        Returns:
            List of missing tracks
        """
        matches = self.match_tracks(spotify_tracks, rekordbox_tracks)
        missing = [m.spotify_track for m in matches if not m.is_match]
        return missing

    def match_tracks(
        self, spotify_tracks: list[Track], rekordbox_tracks: list[RekordboxTrack]
    ) -> list[MatchResult]:
        """Match Spotify tracks with rekordbox collection.

        Args:
            spotify_tracks: List of tracks from Spotify playlist
            rekordbox_tracks: List of tracks from rekordbox collection

        Returns:
            List of MatchResult objects
        """
        # Create search strings for rekordbox tracks
        rekordbox_search_strings = [
            self._create_search_string(track) for track in rekordbox_tracks
        ]

        results: list[MatchResult] = []

        for spotify_track in spotify_tracks:
            search_string = self._create_search_string(spotify_track)
            best_match = self._find_best_match(
                search_string, rekordbox_search_strings, rekordbox_tracks
            )

            if best_match:
                rekordbox_track, score = best_match
                is_match = score >= self.threshold
            else:
                rekordbox_track = None
                score = 0.0
                is_match = False

            results.append(
                MatchResult(
                    spotify_track=spotify_track,
                    rekordbox_track=rekordbox_track,
                    match_score=score,
                    is_match=is_match,
                )
            )

        return results

    def _create_search_string(self, track: Track | RekordboxTrack) -> str:
        """Create a normalized search string from track.

        Args:
            track: Track object (Spotify or rekordbox)

        Returns:
            Normalized search string
        """
        artist = track.normalize_artist()
        title = track.normalize_title()
        return f"{artist} {title}"

    def _find_best_match(
        self,
        search_string: str,
        rekordbox_search_strings: list[str],
        rekordbox_tracks: list[RekordboxTrack],
    ) -> tuple[RekordboxTrack, float] | None:
        """Find the best matching rekordbox track.

        Args:
            search_string: Normalized search string to match
            rekordbox_search_strings: List of normalized search strings
            rekordbox_tracks: List of rekordbox tracks

        Returns:
            Tuple of (best matching track, score) or None if no good match
        """
        if not rekordbox_search_strings:
            return None

        # Use rapidfuzz to find best match
        result = process.extractOne(
            search_string,
            rekordbox_search_strings,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.threshold,
        )

        if result:
            matched_string, score, index = result
            return (rekordbox_tracks[index], score)

        return None

    def compare_artist_title(
        self, spotify_track: Track, rekordbox_track: RekordboxTrack
    ) -> float:
        """Compare artist and title separately for more accurate matching.

        Args:
            spotify_track: Spotify track
            rekordbox_track: rekordbox track

        Returns:
            Combined match score (0-100)
        """
        artist_score = fuzz.ratio(
            spotify_track.normalize_artist(), rekordbox_track.normalize_artist()
        )
        title_score = fuzz.ratio(
            spotify_track.normalize_title(), rekordbox_track.normalize_title()
        )

        # Weighted average (title is more important)
        combined_score = (artist_score * 0.4) + (title_score * 0.6)
        return combined_score


def generate_missing_tracks_report(
    missing_tracks: list[Track], output_path: str | None = None
) -> str:
    """Generate a report of missing tracks.

    Args:
        missing_tracks: List of missing tracks
        output_path: Optional path to save report file

    Returns:
        Report text
    """
    report_lines = [
        f"Missing Tracks Report",
        f"=" * 50,
        f"Total missing tracks: {len(missing_tracks)}",
        "",
    ]

    for i, track in enumerate(missing_tracks, 1):
        report_lines.append(f"{i}. {track.artist} - {track.title}")
        if track.album:
            report_lines.append(f"   Album: {track.album}")
        if track.spotify_url:
            report_lines.append(f"   Spotify: {track.spotify_url}")
        report_lines.append("")

    report_text = "\n".join(report_lines)

    if output_path:
        from pathlib import Path

        Path(output_path).write_text(report_text, encoding="utf-8")
        print(f"Report saved to {output_path}")

    return report_text


def main() -> None:
    """Example usage."""
    import json
    import sys
    from pathlib import Path

    try:
        from rekordbox_parser import RekordboxTrack
        from spotify_client import Track
    except ImportError:
        from .rekordbox_parser import RekordboxTrack
        from .spotify_client import Track

    if len(sys.argv) < 3:
        print("Usage: python track_matcher.py <spotify_json> <rekordbox_json>")
        sys.exit(1)

    spotify_file = Path(sys.argv[1])
    rekordbox_file = Path(sys.argv[2])

    # Load tracks
    with spotify_file.open() as f:
        spotify_data = json.load(f)
    spotify_tracks = [Track(**t) for t in spotify_data]

    with rekordbox_file.open() as f:
        rekordbox_data = json.load(f)
    rekordbox_tracks = [RekordboxTrack(**t) for t in rekordbox_data]

    # Match tracks
    matcher = TrackMatcher(threshold=85.0)
    matches = matcher.match_tracks(spotify_tracks, rekordbox_tracks)

    # Find missing
    missing = matcher.find_missing_tracks(spotify_tracks, rekordbox_tracks)

    print(f"Spotify tracks: {len(spotify_tracks)}")
    print(f"rekordbox tracks: {len(rekordbox_tracks)}")
    print(f"Matched: {len([m for m in matches if m.is_match])}")
    print(f"Missing: {len(missing)}")

    # Generate report
    report = generate_missing_tracks_report(missing, "missing_tracks.txt")
    print("\n" + report)


if __name__ == "__main__":
    main()

