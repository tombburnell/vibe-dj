"""rekordbox collection updater.

Updates track database with rekordbox collection status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from rekordbox_parser import RekordboxParser
    from track_db import TrackDatabase
except ImportError:
    from .rekordbox_parser import RekordboxParser
    from .track_db import TrackDatabase


def update_from_rekordbox(db: TrackDatabase, rekordbox_xml: Path | str) -> None:
    """Update database tracks with rekordbox collection status.

    Args:
        db: TrackDatabase instance
        rekordbox_xml: Path to rekordbox XML export file
    """
    rekordbox_xml = Path(rekordbox_xml)
    
    print(f"Loading rekordbox collection from: {rekordbox_xml}")
    parser = RekordboxParser()
    rekordbox_tracks = parser.parse_xml(rekordbox_xml)
    
    print(f"Found {len(rekordbox_tracks)} tracks in rekordbox collection")
    print("Matching with database tracks...")
    
    matched = 0
    not_matched = 0
    
    # Create a simple matcher for rekordbox tracks
    from rapidfuzz import fuzz
    
    for rb_track in rekordbox_tracks:
        # Try to find matching track in database
        best_match = None
        best_score = 0.0
        best_db_track = None
        
        rb_search = f"{rb_track.normalize_artist()} {rb_track.normalize_title()}"
        
        for db_track in db:
            db_search = f"{db_track.normalize_artist()} {db_track.normalize_title()}"
            score = fuzz.token_sort_ratio(rb_search, db_search)
            
            if score > best_score and score >= 85.0:
                best_score = score
                best_db_track = db_track
        
        if best_db_track:
            # Update track
            updates: dict[str, Any] = {
                "in_rekordbox": True,
                "rekordbox_file_path": rb_track.file_path,
            }
            
            # Also update album if missing
            if not best_db_track.album and rb_track.album:
                updates["album"] = rb_track.album
            
            db.update_track(best_db_track.id, updates)
            matched += 1
        else:
            not_matched += 1
    
    print(f"\nMatched: {matched} tracks")
    print(f"Not matched: {not_matched} rekordbox tracks (not in database)")
    
    db.save()
    print("Database updated and saved.")


def main() -> None:
    """CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update track database from rekordbox")
    parser.add_argument(
        "xml_file",
        type=Path,
        help="Path to rekordbox XML export file",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("music_db.json"),
        help="Path to database file (default: music_db.json)",
    )
    
    args = parser.parse_args()
    
    db = TrackDatabase(args.db)
    update_from_rekordbox(db, args.xml_file)


if __name__ == "__main__":
    main()
