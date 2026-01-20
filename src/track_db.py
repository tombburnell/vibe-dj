"""Track database management system.

Manages a JSON-based database of tracks with playlist tracking,
download status, rekordbox collection status, and Amazon links.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz


@dataclass
class Track:
    """Extended track with database fields."""

    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    spotify_id: str | None = None
    spotify_url: str | None = None
    playlists: list[str] = field(default_factory=list)
    amazon_url: str | None = None
    amazon_search_url: str | None = None
    amazon_price: str | None = None
    amazon_last_searched: str | None = None
    in_rekordbox: bool = False
    rekordbox_file_path: str | None = None
    downloaded: bool = False
    download_path: str | None = None
    download_date: str | None = None
    last_updated: str | None = None
    id: str | None = None  # Will be generated if not provided

    def __post_init__(self) -> None:
        """Generate ID if not provided."""
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

    def to_dict(self) -> dict[str, Any]:
        """Convert track to dictionary."""
        return asdict(self)

    def normalize_artist(self) -> str:
        """Normalize artist name for comparison."""
        return self.artist.strip().lower()

    def normalize_title(self) -> str:
        """Normalize title for comparison."""
        return self.title.strip().lower()

    def merge(self, other: Track) -> Track:
        """Merge another track into this one (for deduplication).

        Args:
            other: Track to merge

        Returns:
            Updated track
        """
        # Merge playlists (union)
        combined_playlists = list(set(self.playlists + other.playlists))
        self.playlists = combined_playlists

        # Prefer non-null values
        if not self.album and other.album:
            self.album = other.album
        if not self.duration_ms and other.duration_ms:
            self.duration_ms = other.duration_ms
        if not self.spotify_id and other.spotify_id:
            self.spotify_id = other.spotify_id
        if not self.spotify_url and other.spotify_url:
            self.spotify_url = other.spotify_url

        # Update timestamp
        self.last_updated = datetime.now(timezone.utc).isoformat()

        return self


class TrackDatabase:
    """Manages track database in JSON format."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database.

        Args:
            db_path: Path to JSON database file
        """
        self.db_path = Path(db_path)
        self.data: dict[str, Any] = {
            "tracks": [],
            "metadata": {
                "version": "1.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "playlists": {},
            },
        }
        self._load()

    def _load(self) -> None:
        """Load database from file."""
        if self.db_path.exists():
            try:
                with self.db_path.open("r", encoding="utf-8") as f:
                    self.data = json.load(f)
                # Convert track dicts to Track objects
                self.data["tracks"] = [
                    Track(**track_dict) for track_dict in self.data["tracks"]
                ]
            except Exception as e:
                print(f"Warning: Failed to load database: {e}")
                print("Starting with empty database")

    def save(self, backup: bool = True) -> None:
        """Save database to file.

        Args:
            backup: Whether to create backup before saving
        """
        if backup and self.db_path.exists():
            backup_path = self.db_path.with_suffix(
                f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy2(self.db_path, backup_path)

        # Update metadata
        self.data["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Convert Track objects to dicts
        tracks_dict = [track.to_dict() for track in self.data["tracks"]]

        # Save to file
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump(
                {"tracks": tracks_dict, "metadata": self.data["metadata"]},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def find_track(
        self, track: Track, threshold: float = 85.0
    ) -> tuple[Track | None, float]:
        """Find matching track in database.

        Args:
            track: Track to find
            threshold: Minimum match score (0-100)

        Returns:
            Tuple of (found track, match score) or (None, 0.0)
        """
        # First try exact match by ID
        if track.id:
            for db_track in self.data["tracks"]:
                if db_track.id == track.id:
                    return (db_track, 100.0)

        # Try spotify_id match
        if track.spotify_id:
            for db_track in self.data["tracks"]:
                if db_track.spotify_id == track.spotify_id:
                    return (db_track, 100.0)

        # Fuzzy match on artist + title
        best_match: Track | None = None
        best_score = 0.0

        search_string = f"{track.normalize_artist()} {track.normalize_title()}"

        for db_track in self.data["tracks"]:
            db_string = f"{db_track.normalize_artist()} {db_track.normalize_title()}"
            score = fuzz.token_sort_ratio(search_string, db_string)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = db_track

        if best_match:
            return (best_match, best_score)

        return (None, 0.0)

    def add_track(self, track: Track, playlist_name: str | None = None) -> Track:
        """Add or update track in database.

        Args:
            track: Track to add
            playlist_name: Optional playlist name to associate with track

        Returns:
            The track (merged if duplicate found)
        """
        # Add playlist if provided
        if playlist_name and playlist_name not in track.playlists:
            track.playlists.append(playlist_name)

        # Check for duplicates
        existing_track, match_score = self.find_track(track)

        if existing_track:
            # Merge with existing track
            existing_track.merge(track)
            return existing_track
        else:
            # Add new track
            self.data["tracks"].append(track)
            return track

    def update_track(self, track_id: str, updates: dict[str, Any]) -> Track | None:
        """Update track fields.

        Args:
            track_id: Track ID to update
            updates: Dictionary of fields to update

        Returns:
            Updated track or None if not found
        """
        for track in self.data["tracks"]:
            if track.id == track_id:
                for key, value in updates.items():
                    if hasattr(track, key):
                        setattr(track, key, value)
                track.last_updated = datetime.now(timezone.utc).isoformat()
                return track
        return None

    def get_tracks_without_amazon_links(self) -> list[Track]:
        """Get tracks that don't have Amazon links.

        Returns:
            List of tracks without amazon_url (search_url is allowed)
        """
        return [
            track
            for track in self.data["tracks"]
            if not track.amazon_url
        ]

    def get_missing_tracks(self) -> list[Track]:
        """Get tracks that are not downloaded and not in rekordbox.

        Returns:
            List of missing tracks
        """
        return [
            track
            for track in self.data["tracks"]
            if not track.downloaded and not track.in_rekordbox
        ]

    def get_tracks_needing_amazon_links(self, missing_only: bool = False) -> list[Track]:
        """Get tracks that need Amazon links.

        Args:
            missing_only: If True, only return tracks that are missing (not downloaded/in rekordbox)

        Returns:
            List of tracks needing Amazon links (without amazon_url)
        """
        if missing_only:
            tracks = self.get_missing_tracks()
        else:
            tracks = self.get_tracks_without_amazon_links()

        # Filter to only tracks without amazon_url
        return [track for track in tracks if not track.amazon_url]

    def register_playlist(
        self, name: str, source: str, csv_file: str | None = None
    ) -> None:
        """Register a playlist in metadata.

        Args:
            name: Playlist name
            source: Source (e.g., "chosic.com")
            csv_file: Path to CSV file
        """
        if "playlists" not in self.data["metadata"]:
            self.data["metadata"]["playlists"] = {}

        self.data["metadata"]["playlists"][name] = {
            "name": name,
            "source": source,
            "csv_file": csv_file,
            "last_imported": datetime.now(timezone.utc).isoformat(),
        }

    def __len__(self) -> int:
        """Return number of tracks in database."""
        return len(self.data["tracks"])

    def __iter__(self):
        """Iterate over tracks."""
        return iter(self.data["tracks"])


def main() -> None:
    """CLI interface for track database."""
    import argparse

    parser = argparse.ArgumentParser(description="Track Database Manager")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("music_db.json"),
        help="Path to database file (default: music_db.json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add playlist command
    add_parser = subparsers.add_parser("add-playlist", help="Add tracks from CSV playlist")
    add_parser.add_argument("csv_file", type=Path, help="Path to CSV file")
    add_parser.add_argument("--name", required=True, help="Playlist name")

    # Update rekordbox command
    rb_parser = subparsers.add_parser(
        "update-rekordbox", help="Update tracks from rekordbox XML"
    )
    rb_parser.add_argument("xml_file", type=Path, help="Path to rekordbox XML file")

    # Fetch Amazon links command
    amazon_parser = subparsers.add_parser(
        "fetch-amazon-links", help="Fetch Amazon links for tracks"
    )
    amazon_parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only fetch links for missing tracks",
    )
    amazon_parser.add_argument(
        "--spotify-id",
        type=str,
        help="Fetch links for a specific track by Spotify ID",
    )
    amazon_parser.add_argument(
        "--track-id",
        type=str,
        help="Fetch links for a specific track by database track ID",
    )
    amazon_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if amazon_url already exists",
    )

    # Scan downloads command
    scan_parser = subparsers.add_parser(
        "scan-downloads", help="Scan directory and mark tracks as downloaded"
    )
    scan_parser.add_argument("directory", type=Path, help="Directory to scan")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db = TrackDatabase(args.db)

    if args.command == "add-playlist":
        try:
            from spotify_client import SpotifyPlaylistExtractor
        except ImportError:
            from .spotify_client import SpotifyPlaylistExtractor

        print(f"Adding playlist '{args.name}' from {args.csv_file}")
        extractor = SpotifyPlaylistExtractor()
        csv_tracks = extractor.parse_csv(args.csv_file)

        added = 0
        updated = 0
        for csv_track in csv_tracks:
            # Convert CSV track to database Track
            db_track = Track(
                title=csv_track.title,
                artist=csv_track.artist,
                album=csv_track.album,
                duration_ms=csv_track.duration_ms,
                spotify_id=csv_track.spotify_id,
                spotify_url=csv_track.spotify_url,
            )
            
            existing = db.find_track(db_track)[0]
            db.add_track(db_track, args.name)
            if existing:
                updated += 1
            else:
                added += 1

        db.register_playlist(args.name, "chosic.com", str(args.csv_file))
        db.save()
        print(f"Added {added} new tracks, updated {updated} existing tracks. Total tracks: {len(db)}")

    elif args.command == "update-rekordbox":
        try:
            from rekordbox_updater import update_from_rekordbox
        except ImportError:
            from .rekordbox_updater import update_from_rekordbox
        
        update_from_rekordbox(db, args.xml_file)

    elif args.command == "fetch-amazon-links":
        import time
        
        # Filter by specific track if requested
        if args.spotify_id or args.track_id:
            # When filtering by specific track, search all tracks
            tracks = []
            
            if args.spotify_id:
                for track in db:
                    if track.spotify_id == args.spotify_id:
                        tracks.append(track)
                        break
                if not tracks:
                    print(f"Error: No track found with Spotify ID: {args.spotify_id}")
                    return
            
            elif args.track_id:
                for track in db:
                    if track.id == args.track_id:
                        tracks.append(track)
                        break
                if not tracks:
                    print(f"Error: No track found with track ID: {args.track_id}")
                    return
            
            # Check if track already has amazon_url (unless --force)
            if tracks and tracks[0].amazon_url and not args.force:
                print(f"Error: Track '{tracks[0].artist} - {tracks[0].title}' already has Amazon URL:")
                print(f"  {tracks[0].amazon_url}")
                print("Use --force to override and re-fetch.")
                return
        else:
            tracks = db.get_tracks_needing_amazon_links(missing_only=args.missing_only)
        
        # Filter out tracks with amazon_url unless --force
        if not args.force and (args.spotify_id or args.track_id):
            # Already handled above for specific tracks
            pass
        elif not args.force:
            # Filter out tracks that already have amazon_url
            tracks = [t for t in tracks if not t.amazon_url]
        
        print(f"Found {len(tracks)} tracks needing Amazon links")
        
        if not tracks:
            print("No tracks need Amazon links.")
            return
        
        try:
            from amazon_music import AmazonMusicSearcher
        except ImportError:
            from .amazon_music import AmazonMusicSearcher
        
        searcher = AmazonMusicSearcher()
        updated = 0
        errors = 0
        
        for i, track in enumerate(tracks, 1):
            print(f"\n[{i}/{len(tracks)}] Searching for: {track.artist} - {track.title}")
            
            # Rate limiting: wait between requests to avoid 503s
            if i > 1:
                wait_time = 2.0  # 2 seconds between requests
                print(f"  Waiting {wait_time}s to avoid rate limiting...")
                time.sleep(wait_time)
            
            try:
                # Try to get specific results
                try:
                    results = searcher.search_track(track)
                    
                    if results and results[0].url:
                        # Found a direct link - update database
                        amazon_search_url = searcher.generate_amazon_link(track)
                        db.update_track(
                            track.id,
                            {
                                "amazon_url": results[0].url,
                                "amazon_search_url": amazon_search_url,
                                "amazon_price": results[0].price,
                                "amazon_last_searched": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                        print(f"  ✓ Found: {results[0].url} ({results[0].price or 'no price'})")
                        updated += 1
                    else:
                        # No results found - don't update database
                        print(f"  ✗ No Amazon links found")
                except Exception as search_error:
                    # Amazon search failed - don't update database
                    print(f"  ⚠ Search failed: {search_error}")
                    errors += 1
                    
                    # If we're getting too many errors, slow down more
                    if errors > 5:
                        print(f"  ⚠ Too many errors, increasing delay to 5s...")
                        time.sleep(3.0)  # Extra delay
                
                # Save periodically (every 10 tracks)
                if i % 10 == 0:
                    db.save(backup=False)
                    print(f"  [Saved progress: {i}/{len(tracks)}]")
                    
            except Exception as e:
                print(f"  ✗ Error: {e}")
                errors += 1
                # Still mark as searched to avoid retrying immediately
                db.update_track(
                    track.id,
                    {"amazon_last_searched": datetime.now(timezone.utc).isoformat()},
                )
                continue
        
        # Final save
        db.save()
        print(f"\n✓ Updated {updated}/{len(tracks)} tracks with Amazon links")
        if errors > 0:
            print(f"⚠ {errors} tracks had errors (but search URLs were saved)")

    elif args.command == "scan-downloads":
        try:
            from download_scanner import scan_directory
        except ImportError:
            from .download_scanner import scan_directory
        
        scan_directory(db, args.directory)


if __name__ == "__main__":
    main()
