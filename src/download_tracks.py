"""Main orchestration script for music collection automation.

Downloads Spotify playlists, compares with rekordbox collection,
and generates Amazon Music purchase links for missing tracks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from amazon_music import AmazonMusicSearcher, generate_amazon_report
    from rekordbox_parser import RekordboxParser
    from spotify_client import SpotifyPlaylistExtractor
    from track_matcher import TrackMatcher, generate_missing_tracks_report
except ImportError:
    from .amazon_music import AmazonMusicSearcher, generate_amazon_report
    from .rekordbox_parser import RekordboxParser
    from .spotify_client import SpotifyPlaylistExtractor
    from .track_matcher import TrackMatcher, generate_missing_tracks_report


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare Spotify playlists with rekordbox collection "
        "and generate Amazon Music purchase links for missing tracks"
    )

    parser.add_argument(
        "spotify_playlist",
        help="Spotify playlist URL or ID (e.g., "
        "https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH)",
    )

    parser.add_argument(
        "--rekordbox-xml",
        type=Path,
        help="Path to rekordbox XML export file",
    )

    parser.add_argument(
        "--rekordbox-db",
        type=Path,
        help="Path to rekordbox database file (optional, uses default if not specified)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory for reports and JSON files (default: ./output)",
    )

    parser.add_argument(
        "--match-threshold",
        type=float,
        default=85.0,
        help="Fuzzy match threshold (0-100, default: 85.0)",
    )

    parser.add_argument(
        "--skip-amazon",
        action="store_true",
        help="Skip Amazon Music search (faster, only generates missing tracks list)",
    )

    parser.add_argument(
        "--export-json",
        action="store_true",
        help="Export intermediate JSON files (spotify_tracks.json, rekordbox_tracks.json)",
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Music Collection Automation")
    print("=" * 60)
    print()

    # Step 1: Extract Spotify playlist
    print("Step 1: Extracting Spotify playlist...")
    try:
        spotify_extractor = SpotifyPlaylistExtractor()
        spotify_tracks = spotify_extractor.get_playlist_tracks(args.spotify_playlist)
        print(f"✓ Found {len(spotify_tracks)} tracks in Spotify playlist")
    except Exception as e:
        print(f"✗ Error extracting Spotify playlist: {e}")
        sys.exit(1)

    if args.export_json:
        spotify_json = args.output_dir / "spotify_tracks.json"
        spotify_extractor.export_to_json(spotify_tracks, spotify_json)

    # Step 2: Parse rekordbox collection
    print("\nStep 2: Parsing rekordbox collection...")
    rekordbox_tracks: list = []
    rekordbox_parser = RekordboxParser()

    if args.rekordbox_db:
        try:
            rekordbox_tracks = rekordbox_parser.parse_database(args.rekordbox_db)
            print(f"✓ Found {len(rekordbox_tracks)} tracks in rekordbox database")
        except Exception as e:
            print(f"✗ Error parsing rekordbox database: {e}")
            sys.exit(1)
    elif args.rekordbox_xml:
        try:
            rekordbox_tracks = rekordbox_parser.parse_xml(args.rekordbox_xml)
            print(f"✓ Found {len(rekordbox_tracks)} tracks in rekordbox XML")
        except Exception as e:
            print(f"✗ Error parsing rekordbox XML: {e}")
            sys.exit(1)
    else:
        print("✗ Error: Must provide either --rekordbox-xml or --rekordbox-db")
        sys.exit(1)

    if args.export_json:
        rekordbox_json = args.output_dir / "rekordbox_tracks.json"
        rekordbox_parser.export_to_json(rekordbox_tracks, rekordbox_json)

    # Step 3: Match tracks
    print("\nStep 3: Comparing tracks...")
    try:
        matcher = TrackMatcher(threshold=args.match_threshold)
        matches = matcher.match_tracks(spotify_tracks, rekordbox_tracks)
        matched_count = len([m for m in matches if m.is_match])
        missing_tracks = matcher.find_missing_tracks(spotify_tracks, rekordbox_tracks)

        print(f"✓ Matched: {matched_count}/{len(spotify_tracks)} tracks")
        print(f"✓ Missing: {len(missing_tracks)} tracks")
    except Exception as e:
        print(f"✗ Error matching tracks: {e}")
        sys.exit(1)

    # Step 4: Generate missing tracks report
    print("\nStep 4: Generating missing tracks report...")
    missing_report_path = args.output_dir / "missing_tracks.txt"
    try:
        report_text = generate_missing_tracks_report(
            missing_tracks, str(missing_report_path)
        )
        print(f"✓ Report saved to {missing_report_path}")
    except Exception as e:
        print(f"✗ Error generating report: {e}")
        sys.exit(1)

    # Step 5: Generate Amazon Music links (optional)
    if not args.skip_amazon and missing_tracks:
        print("\nStep 5: Searching Amazon Music...")
        amazon_report_path = args.output_dir / "amazon_links.txt"
        try:
            amazon_report = generate_amazon_report(
                missing_tracks, str(amazon_report_path)
            )
            print(f"✓ Amazon links report saved to {amazon_report_path}")
        except Exception as e:
            print(f"⚠ Warning: Error generating Amazon links: {e}")
            print("  You can still use the missing_tracks.txt file manually")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Spotify tracks: {len(spotify_tracks)}")
    print(f"rekordbox tracks: {len(rekordbox_tracks)}")
    print(f"Matched: {matched_count}")
    print(f"Missing: {len(missing_tracks)}")
    print(f"\nReports saved to: {args.output_dir}")
    print("  - missing_tracks.txt")
    if not args.skip_amazon:
        print("  - amazon_links.txt")
    print()


if __name__ == "__main__":
    main()

