"""Download scanner.

Scans file system for downloaded music files and updates database.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from track_db import TrackDatabase
except ImportError:
    from .track_db import TrackDatabase


def scan_directory(db: TrackDatabase, directory: Path | str) -> None:
    """Scan directory for music files and mark tracks as downloaded.

    Args:
        db: TrackDatabase instance
        directory: Directory to scan
    """
    directory = Path(directory)
    
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    # Music file extensions
    music_extensions = {".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".wma"}
    
    print(f"Scanning directory: {directory}")
    print("Looking for music files...")
    
    music_files: list[Path] = []
    for ext in music_extensions:
        music_files.extend(directory.rglob(f"*{ext}"))
        music_files.extend(directory.rglob(f"*{ext.upper()}"))
    
    print(f"Found {len(music_files)} music files")
    print("Matching files to database tracks...")
    
    matched = 0
    not_matched = 0
    
    from rapidfuzz import fuzz
    from datetime import datetime
    
    for file_path in music_files:
        # Extract potential artist and title from filename
        # Common patterns: "Artist - Title.mp3", "Artist/Title.mp3", etc.
        filename = file_path.stem  # Without extension
        
        # Try to parse filename
        artist = None
        title = None
        
        # Pattern: "Artist - Title"
        if " - " in filename:
            parts = filename.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else filename
        # Pattern: "Artist/Title"
        elif "/" in filename:
            parts = filename.rsplit("/", 1)
            artist = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else filename
        else:
            # Just use filename as title
            title = filename
        
        # Try to find matching track in database
        best_match = None
        best_score = 0.0
        best_db_track = None
        
        if artist and title:
            file_search = f"{artist.lower()} {title.lower()}"
        else:
            file_search = title.lower() if title else filename.lower()
        
        for db_track in db:
            if db_track.downloaded:
                continue  # Skip already marked tracks
            
            db_search = f"{db_track.normalize_artist()} {db_track.normalize_title()}"
            score = fuzz.token_sort_ratio(file_search, db_search)
            
            # Also try matching just title if artist not found
            if not artist:
                title_score = fuzz.token_sort_ratio(
                    title.lower() if title else filename.lower(),
                    db_track.normalize_title(),
                )
                score = max(score, title_score * 0.8)  # Weight title-only matches lower
            
            if score > best_score and score >= 80.0:
                best_score = score
                best_db_track = db_track
        
        if best_db_track:
            # Update track
            updates: dict[str, Any] = {
                "downloaded": True,
                "download_path": str(file_path.absolute()),
                "download_date": datetime.utcnow().isoformat(),
            }
            
            db.update_track(best_db_track.id, updates)
            matched += 1
            print(f"  ✓ Matched: {best_db_track.artist} - {best_db_track.title}")
        else:
            not_matched += 1
    
    print(f"\nMatched: {matched} files to database tracks")
    print(f"Not matched: {not_matched} files (not in database or already marked)")
    
    db.save()
    print("Database updated and saved.")


def main() -> None:
    """CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan directory and mark tracks as downloaded")
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to scan for music files",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("music_db.json"),
        help="Path to database file (default: music_db.json)",
    )
    
    args = parser.parse_args()
    
    db = TrackDatabase(args.db)
    scan_directory(db, args.directory)


if __name__ == "__main__":
    main()
