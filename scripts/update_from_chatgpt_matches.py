#!/usr/bin/env python3
"""Update database from ChatGPT matching results.

Usage:
    python scripts/update_from_chatgpt_matches.py matches.json [--min-confidence 0.6] [--confidence-delta 0.1]
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.track_db import TrackDatabase


def update_from_matches(
    db: TrackDatabase,
    matches_file: Path,
    min_confidence: float = 0.6,
    confidence_delta: float = 0.1,
) -> None:
    """Update database from ChatGPT matching results.

    Args:
        db: TrackDatabase instance
        matches_file: Path to JSON file with matches from ChatGPT
        min_confidence: Minimum confidence to update (default: 0.6)
        confidence_delta: Minimum improvement to update existing match (default: 0.1)
    """
    # Load matches
    with matches_file.open("r", encoding="utf-8") as f:
        matches = json.load(f)

    updated = 0
    skipped_low_confidence = 0
    skipped_lower_confidence = 0
    not_found = 0

    for match in matches:
        track_id = match["id"]
        rekordbox_path = match["rekordbox_file_path"]
        confidence = match["confidence"]

        # Find track in database
        track = None
        for db_track in db:
            if db_track.id == track_id:
                track = db_track
                break

        if not track:
            print(f"Warning: Track {track_id} not found in database")
            not_found += 1
            continue

        # Check confidence threshold
        if confidence < min_confidence:
            print(
                f"Skipping {track.artist} - {track.title}: confidence {confidence:.2f} < {min_confidence}"
            )
            skipped_low_confidence += 1
            continue

        # Check if we should update existing match
        current_confidence = getattr(track, "rekordbox_match_confidence", None)
        if track.rekordbox_file_path and current_confidence is not None:
            if confidence <= current_confidence + confidence_delta:
                print(
                    f"Skipping {track.artist} - {track.title}: "
                    f"new confidence {confidence:.2f} not significantly higher than {current_confidence:.2f}"
                )
                skipped_lower_confidence += 1
                continue

        # Update track
        updates = {
            "rekordbox_file_path": rekordbox_path,
            "in_rekordbox": True,
            "rekordbox_match_confidence": confidence,
        }

        db.update_track(track_id, updates)
        updated += 1
        print(
            f"Updated {track.artist} - {track.title}: "
            f"confidence {confidence:.2f} → {rekordbox_path}"
        )

    # Save database
    db.save()

    print(f"\nSummary:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (low confidence): {skipped_low_confidence}")
    print(f"  Skipped (lower confidence): {skipped_lower_confidence}")
    print(f"  Not found: {not_found}")


def main() -> None:
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Update database from ChatGPT matching results"
    )
    parser.add_argument(
        "matches_file", type=Path, help="JSON file with matches from ChatGPT"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence to update (default: 0.6)",
    )
    parser.add_argument(
        "--confidence-delta",
        type=float,
        default=0.1,
        help="Minimum improvement to update existing match (default: 0.1)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("music_db.json"),
        help="Path to database file (default: music_db.json)",
    )

    args = parser.parse_args()

    db = TrackDatabase(args.db)
    update_from_matches(db, args.matches_file, args.min_confidence, args.confidence_delta)


if __name__ == "__main__":
    main()
