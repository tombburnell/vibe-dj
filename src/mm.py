"""Main CLI tool for music collection management.

Commands:
    mm import-rekordbox <tsv_file>  - Import Rekordbox collection and match with existing tracks
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from .amazon_music import AmazonSearchResult
from .amazon_service import calculate_url_score, search_amazon_for_track
from .library_db import LibraryDB, LibraryTrack
from .rekordbox_index import RekordboxIndex
from .rekordbox_tsv_parser import RekordboxTSVParser
from .spotify_client import SpotifyPlaylistExtractor
from .track_matching import calculate_match_score
from .track_normalizer import (
    create_all_tokens,
    create_base_title,
    normalize_text,
)


def format_duration(duration_ms: int | None) -> str:
    """Format duration in milliseconds to min:sec format."""
    if duration_ms is None:
        return "--:--"
    total_seconds = duration_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"




def parse_duration_to_ms(duration_str: str) -> int | None:
    """Parse duration string (MM:SS format) to milliseconds.
    
    Args:
        duration_str: Duration string in MM:SS format (e.g., "4:58", "12:30")
    
    Returns:
        Duration in milliseconds or None if invalid
    """
    if not duration_str or not duration_str.strip():
        return None
    
    try:
        parts = duration_str.strip().split(":")
        if len(parts) != 2:
            return None
        minutes = int(parts[0])
        seconds = int(parts[1])
        total_seconds = minutes * 60 + seconds
        return total_seconds * 1000
    except (ValueError, IndexError):
        return None


def calculate_duration_similarity_score(
    track_duration_ms: int | None, match_duration_ms: int | None
) -> float:
    """Calculate duration similarity score (0-100, compressed upward).
    
    Uses exponential compression so good matches stay high and bad matches
    don't drag down the score too much.
    
    Args:
        track_duration_ms: Track duration in milliseconds
        match_duration_ms: Target duration in milliseconds to match against
    
    Returns:
        Similarity score 0-100 (50 if either duration is missing)
    """
    if not track_duration_ms or not match_duration_ms:
        return 50.0  # Neutral if missing
    
    duration_diff = abs(track_duration_ms - match_duration_ms)
    duration_ratio = duration_diff / match_duration_ms
    
    # Exponential compression: 0% diff = 100, 10% diff = ~90, 30% diff = ~70, 50%+ = 50
    # Compress upward so good matches stay high
    duration_score = max(50.0, 100.0 - (duration_ratio * 100.0 * 1.5))
    
    return duration_score


def search_tracks(
    db_path: Path = Path("music.db"),
    search_query: str = "",
    threshold: float = 60.0,
    limit: int = 20,
    match_duration: str | None = None,
) -> None:
    """Search tracks by query string.

    Args:
        db_path: Path to SQLite database
        search_query: Search query string (space-separated tokens)
        threshold: Minimum match score (0-100)
        limit: Maximum number of results to return (default: 20)
        match_duration: Optional duration to match against (MM:SS format, e.g., "4:58")
    """
    if not search_query:
        logger.error("Search query cannot be empty")
        sys.exit(1)
    
    # Parse match duration if provided
    match_duration_ms: int | None = None
    if match_duration:
        match_duration_ms = parse_duration_to_ms(match_duration)
        if match_duration_ms is None:
            logger.error(f"Invalid duration format: {match_duration}. Expected MM:SS (e.g., 4:58)")
            sys.exit(1)

    logger.info(f"Searching tracks: '{search_query}'")
    if match_duration_ms:
        logger.info(f"Matching duration: {format_duration(match_duration_ms)}")

    db = LibraryDB(db_path)
    all_tracks = db.get_all_tracks()

    if not all_tracks:
        logger.info("No tracks found in database")
        db.close()
        return

    # Normalize search query and split into tokens
    search_tokens = normalize_text(search_query).split()
    if not search_tokens:
        logger.error("Invalid search query")
        sys.exit(1)

    # Search tracks
    # Updated tuple: (track, final_score, token_scores, track_tokens, duration_score)
    matches: list[tuple[LibraryTrack, float, list[float], list[str], float | None]] = []

    for track in all_tracks:
        # Normalize track fields
        track_artist = normalize_text(track.artist)
        track_title = normalize_text(track.title)
        track_text = f"{track_artist} {track_title}"

        # Calculate score for each token
        token_scores = []
        for token in search_tokens:
            # Split track text into words for word-level matching
            track_words = track_text.split()
            
            # Check if token appears as a word (exact or fuzzy word match)
            best_word_score = 0.0
            for word in track_words:
                # Exact word match = 100
                if token == word:
                    best_word_score = 100.0
                    break
                # Fuzzy word match (for typos/variations)
                word_score = fuzz.ratio(token, word)
                if word_score > best_word_score:
                    best_word_score = word_score
            
            # Also check substring match as fallback (but penalize it)
            # This handles cases like "octave" matching "octave one"
            substring_score = fuzz.partial_ratio(token, track_text)
            
            # Prefer word-level matches, but allow substring matches at reduced score
            if best_word_score >= 80:  # Good word match
                token_score = best_word_score
            elif substring_score >= 90:  # Very strong substring match
                token_score = substring_score * 0.9  # 10% penalty for substring
            else:
                token_score = max(best_word_score, substring_score * 0.7)  # Penalize weak substring matches
            
            token_scores.append(token_score)

        # Calculate text score: average of all token scores
        # Perfect match (all tokens = 100) → text_score = 100
        # Partial match penalized proportionally
        text_score = sum(token_scores) / len(token_scores)
        
        # Calculate duration similarity score if match_duration provided
        duration_score: float | None = None
        if match_duration_ms:
            duration_score = calculate_duration_similarity_score(
                track.duration_ms, match_duration_ms
            )
            
            # Weighted combination: 85% text, 15% duration
            text_weight = 0.85
            duration_weight = 0.15
            final_score = (text_score * text_weight) + (duration_score * duration_weight)
        else:
            final_score = text_score

        # If final score meets threshold, add to matches
        if final_score >= threshold:
            # Get track tokens for display
            track_tokens = track_text.split()
            matches.append((track, final_score, token_scores, track_tokens, duration_score))

    # Sort by score (descending)
    matches.sort(key=lambda x: x[1], reverse=True)  # x[1] is the final_score

    # Apply limit
    total_matches = len(matches)
    matches = matches[:limit]

    # Display results
    if not matches:
        logger.info(f"No tracks found matching '{search_query}' (threshold: {threshold})")
    else:
        if total_matches > limit:
            logger.info(f"Found {total_matches} matching tracks (showing top {limit}):")
        else:
            logger.info(f"Found {total_matches} matching tracks:")
        print()
        print(f"{'Score':<8} {'Artist':<30} {'Title':<40} {'Duration':<10} {'ID':<20} {'Token Scores':<20} {'Track Tokens':<40}")
        print("-" * 170)

        for track, score, token_scores, track_tokens, duration_score in matches:
            artist_display = track.artist[:28] + ".." if len(track.artist) > 30 else track.artist
            title_display = track.title[:38] + ".." if len(track.title) > 40 else track.title
            duration_display = format_duration(track.duration_ms)
            token_scores_str = ",".join(f"{s:.0f}" for s in token_scores)
            # Add duration score in brackets if available
            if duration_score is not None:
                token_scores_str += f" [{duration_score:.0f}]"
            track_tokens_str = " ".join(track_tokens[:8])  # Show first 8 tokens
            if len(track_tokens) > 8:
                track_tokens_str += "..."
            print(f"{score:>6.1f}  {artist_display:<30} {title_display:<40} {duration_display:<10} {track.id:<20} {token_scores_str:<20} {track_tokens_str:<40}")

        print()

    db.close()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def extract_artist_title_from_filename(filename: str) -> tuple[str | None, str]:
    """Extract artist and title from filename using common patterns.
    
    Common patterns:
    - "Artist - Title.mp3"
    - "Artist -- Title.mp3"
    - "Title - Artist.mp3" (less common)
    - "Artist/Title.mp3"
    - Just "Title.mp3" (no artist)
    
    Args:
        filename: Full path or just filename
        
    Returns:
        Tuple of (artist, title) where artist may be None
    """
    # Extract just the filename without path
    path = Path(filename)
    stem = path.stem  # Filename without extension
    
    # Pattern 1: "Artist - Title" or "Artist -- Title"
    if " - " in stem:
        parts = stem.split(" - ", 1)
        if len(parts) == 2:
            return (parts[0].strip(), parts[1].strip())
    elif " -- " in stem:
        parts = stem.split(" -- ", 1)
        if len(parts) == 2:
            return (parts[0].strip(), parts[1].strip())
    
    # Pattern 2: "Artist/Title" (path separator)
    if "/" in stem:
        parts = stem.rsplit("/", 1)
        if len(parts) == 2:
            return (parts[0].strip(), parts[1].strip())
    
    # Pattern 3: Just title (no artist)
    return (None, stem.strip())


def mark_downloaded(
    file_list_path: Path,
    db_path: Path = Path("music.db"),
    threshold: float = 85.0,
) -> None:
    """Mark tracks as downloaded based on a file list.
    
    Reads a text file with one filename per line, extracts artist/title from
    filenames, matches against tracks in DB (where downloaded=False and 
    rekordbox_file_path IS NULL), and updates matched tracks.
    
    Args:
        file_list_path: Path to text file with one filename per line
        db_path: Path to SQLite database
        threshold: Minimum match score (0-100, default: 85.0)
    """
    if not file_list_path.exists():
        logger.error(f"File list not found: {file_list_path}")
        sys.exit(1)
    
    # Read file list
    with file_list_path.open("r", encoding="utf-8") as f:
        filenames = [line.strip() for line in f if line.strip()]
    
    if not filenames:
        logger.warning("File list is empty")
        return
    
    logger.info(f"Processing {len(filenames)} files from {file_list_path}")
    
    # Open database
    db = LibraryDB(db_path)
    
    # Get eligible tracks (not downloaded, no rekordbox path)
    eligible_tracks = db.get_undownloaded_tracks_without_rekordbox()
    logger.info(f"Found {len(eligible_tracks)} eligible tracks in database")
    
    if not eligible_tracks:
        logger.warning("No eligible tracks found in database")
        db.close()
        return
    
    # Build normalized search strings for eligible tracks
    eligible_track_data: list[tuple[LibraryTrack, str]] = []
    for track in eligible_tracks:
        # Use same normalization as find_track
        search_string = f"{track.normalize_artist()} {track.normalize_title()}"
        eligible_track_data.append((track, search_string))
    
    matched_count = 0
    unmatched_files: list[str] = []
    
    # Process each filename
    for filename in filenames:
        artist, title = extract_artist_title_from_filename(filename)
        
        if not title:
            logger.warning(f"Could not extract title from: {filename}")
            unmatched_files.append(filename)
            continue
        
        # Build search string from filename
        if artist:
            file_search = f"{artist.strip().lower()} {title.strip().lower()}"
        else:
            file_search = title.strip().lower()
        
        # Find best match
        best_match: LibraryTrack | None = None
        best_score = 0.0
        
        for db_track, db_search_string in eligible_track_data:
            score = fuzz.token_sort_ratio(file_search, db_search_string)
            
            # If no artist in filename, also try title-only match (weighted lower)
            if not artist:
                title_score = fuzz.token_sort_ratio(
                    title.strip().lower(),
                    db_track.normalize_title(),
                )
                score = max(score, title_score * 0.8)  # Weight title-only matches lower
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = db_track
        
        if best_match:
            # Update track
            download_date = datetime.now(timezone.utc).isoformat()
            db.update_track(
                best_match.id,
                {
                    "downloaded": True,
                    "download_path": filename,
                    "download_date": download_date,
                },
            )
            matched_count += 1
            logger.info(
                f"✓ Matched: {filename} → {best_match.artist} - {best_match.title} (score: {best_score:.1f})"
            )
        else:
            unmatched_files.append(filename)
            logger.debug(f"✗ No match for: {filename} (best score: {best_score:.1f})")
    
    # Commit changes
    db.commit()
    db.close()
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total files processed: {len(filenames)}")
    print(f"  Matched and marked as downloaded: {matched_count}")
    print(f"  Unmatched files: {len(unmatched_files)}")
    print(f"{'='*60}")
    
    # Log unmatched files
    if unmatched_files:
        logger.info("Unmatched files:")
        for filename in unmatched_files:
            logger.info(f"  - {filename}")


def print_match_debug(
    spotify_track,
    spotify_tokens: list[str],
    candidate_ids: list[str],
    matches: list[tuple[LibraryTrack, float]],
    index: RekordboxIndex,
    rekordbox_tsv_tracks: list,
) -> None:
    """Print detailed debug information for a single track match."""
    print("\n" + "="*80)
    print(f"DEBUG: Matching Spotify Track")
    print("="*80)
    print(f"Spotify ID: {spotify_track.spotify_id or 'N/A'}")
    print(f"Title: {spotify_track.title}")
    print(f"Artist: {spotify_track.artist}")
    if spotify_track.album:
        print(f"Album: {spotify_track.album}")
    if spotify_track.duration_ms:
        duration_sec = spotify_track.duration_ms // 1000
        print(f"Duration: {duration_sec // 60}:{duration_sec % 60:02d}")
    
    print(f"\nSpotify Tokens ({len(spotify_tokens)}): {', '.join(spotify_tokens)}")
    
    # Show candidate generation
    print(f"\nCandidate Generation:")
    print(f"  Found {len(candidate_ids)} candidates from index")
    if candidate_ids:
        # Show token overlap for top candidates
        candidate_overlaps: dict[str, int] = {}
        for token in spotify_tokens:
            if token in index.token_index:
                for rb_id in index.token_index[token]:
                    if rb_id in candidate_ids[:10]:  # Top 10 only
                        candidate_overlaps[rb_id] = candidate_overlaps.get(rb_id, 0) + 1
        
        print(f"  Top candidate token overlaps:")
        for rb_id, overlap in sorted(candidate_overlaps.items(), key=lambda x: x[1], reverse=True)[:5]:
            rb_track = index.get_track(rb_id)
            if rb_track:
                print(f"    {overlap} tokens: {rb_track.title[:50]} - {rb_track.artist[:30]}")
    
    print(f"\nMatch Results ({len(matches)} candidates scored):")
    print("-"*80)
    
    for rank, (lib_track, score) in enumerate(matches[:10], 1):  # Show top 10
        # Find corresponding RekordboxTSVTrack
        rb_track = None
        for rt in rekordbox_tsv_tracks:
            if rt.file_path == lib_track.rekordbox_file_path:
                rb_track = rt
                break
        
        if not rb_track:
            continue
        
        # Create temporary LibraryTrack for scoring
        spotify_lib_track = LibraryTrack(
            title=spotify_track.title,
            artist=spotify_track.artist,
            album=spotify_track.album,
            duration_ms=spotify_track.duration_ms,
        )
        
        # Get debug info
        score_0_1, debug = calculate_match_score(
            spotify_lib_track, rb_track, return_debug=True
        )
        
        print(f"\n#{rank} Score: {score:.1f} (confidence: {score_0_1:.3f})")
        print(f"  Rekordbox: {rb_track.title} - {rb_track.artist}")
        print(f"  File: {rb_track.file_path}")
        
        title_debug = debug["title_debug"]
        print(f"\n  Title Matching:")
        print(f"    Spotify base title: '{title_debug['title_a_base']}'")
        print(f"    Rekordbox base title: '{title_debug['title_b_base']}'")
        print(f"    Title tokens (Spotify): {title_debug['tokens_a']}")
        print(f"    Title tokens (Rekordbox): {title_debug['tokens_b']}")
        if title_debug["removed_tokens_a"] or title_debug["removed_tokens_b"]:
            print(
                f"    Removed tokens (Spotify): {title_debug['removed_tokens_a']}"
            )
            print(
                f"    Removed tokens (Rekordbox): {title_debug['removed_tokens_b']}"
            )
        print(f"    Title coverage: {title_debug['coverage']:.3f}")
        print(f"    Title quality: {title_debug['quality']:.3f}")
        print(f"    Title order score: {title_debug['order_score']:.3f}")
        print("    Title token scores:")
        for detail in title_debug["details"]:
            best = detail.best_match or "—"
            print(
                f"      '{detail.token}': {detail.score:.3f} (→ {best}), weight={detail.weight:.3f}"
            )
        
        artist_debug = debug["artist_debug"]
        print(f"\n  Artist Matching:")
        print(f"    Primary artist tokens: {artist_debug['primary_tokens']}")
        print(f"    Extra artist tokens: {artist_debug['extra_tokens']}")
        print(f"    Rekordbox artist tokens: {artist_debug['rekordbox_tokens']}")
        print(f"    Primary coverage: {artist_debug['primary_coverage']:.3f}")
        print(f"    Primary quality: {artist_debug['primary_quality']:.3f}")
        print("    Primary token scores:")
        for detail in artist_debug["primary_details"]:
            best = detail.best_match or "—"
            print(
                f"      '{detail.token}': {detail.score:.3f} (→ {best}), weight={detail.weight:.3f}"
            )
        print(f"    Extra coverage: {artist_debug['extra_coverage']:.3f}")
        print(f"    Extra quality: {artist_debug['extra_quality']:.3f}")
        print("    Extra token scores:")
        for detail in artist_debug["extra_details"]:
            best = detail.best_match or "—"
            print(
                f"      '{detail.token}': {detail.score:.3f} (→ {best}), weight={detail.weight:.3f}"
            )
        
        duration_debug = debug["duration_debug"]
        lib_ms = spotify_lib_track.duration_ms
        rb_ms = rb_track.duration_ms
        lib_dur = f"{lib_ms // 60000}:{(lib_ms // 1000) % 60:02d}" if lib_ms else "N/A"
        rb_dur = f"{rb_ms // 60000}:{(rb_ms // 1000) % 60:02d}" if rb_ms else "N/A"
        diff_ratio = duration_debug["diff_ratio"]
        diff_pct = f"{diff_ratio * 100:.1f}%" if diff_ratio is not None else "N/A"

        print(f"\n  Score Calculation:")
        print(
            f"    Text score: {debug['text_score']:.3f} (title: {debug['title_score']:.3f}, artist: {debug['artist_score']:.3f})"
        )
        variation_debug = debug["variation_debug"]
        print(
            f"    Variation tokens (Spotify): {variation_debug['tokens_a']}"
        )
        print(
            f"    Variation tokens (Rekordbox): {variation_debug['tokens_b']}"
        )
        print(
            f"    Variation overlap: {variation_debug['overlap']} (match: {variation_debug['match']:.3f})"
        )
        missing_debug = debug["missing_debug"]
        print(
            f"    Missing tokens (Spotify): {missing_debug['missing_a']}"
        )
        print(
            f"    Missing tokens (Rekordbox): {missing_debug['missing_b']}"
        )
        print(
            f"    Missing ratio: {missing_debug['missing_ratio']:.3f}"
        )
        print(
            f"    Duration: Spotify {lib_dur} vs Rekordbox {rb_dur} (diff {diff_pct})"
        )
        print(f"    Duration score: {debug['duration_score']:.3f}")
        print(f"    Variation penalty: {debug['variation_penalty']:.3f}")
        print(f"    Missing penalty: {debug['missing_penalty']:.3f}")
        print(f"    Final score: {debug['final_score']:.3f}")
        
        print("-"*80)
    
    print("\n" + "="*80)


def import_rekordbox(
    tsv_path: Path,
    db_path: Path = Path("music.db"),
    min_confidence: float = 0.6,
    add_unmatched: bool = False,
) -> None:
    """Import Rekordbox collection and match with existing tracks.

    Args:
        tsv_path: Path to Rekordbox TSV export file
        db_path: Path to SQLite database
        min_confidence: Minimum confidence score to update (0.0-1.0)
        add_unmatched: Whether to add unmatched Rekordbox tracks as new LibraryTracks
    """
    logger.info(f"Parsing Rekordbox TSV file: {tsv_path}")
    parser = RekordboxTSVParser()
    rekordbox_tracks = parser.parse_tsv(tsv_path)
    logger.info(f"Parsed {len(rekordbox_tracks)} Rekordbox tracks")

    logger.info("Building inverted index...")
    index = RekordboxIndex(rekordbox_tracks)
    index.build_index(rekordbox_tracks)
    logger.info(f"Index built: {len(index.tracks)} tracks, {len(index.token_index)} tokens")

    logger.info("Loading existing tracks from database...")
    db = LibraryDB(db_path)
    library_tracks = db.get_all_tracks()
    logger.info(f"Loaded {len(library_tracks)} tracks from database")

    # Track statistics
    matched_count = 0
    updated_count = 0
    created_count = 0
    skipped_count = 0

    # Match each LibraryTrack against Rekordbox collection
    logger.info("Matching tracks...")
    for library_track in library_tracks:
        # Skip if already matched to Rekordbox AND has duration_ms
        # (allow re-matching if duration_ms is missing)
        if library_track.in_rekordbox and library_track.duration_ms:
            skipped_count += 1
            continue

        # Generate tokens from LibraryTrack
        library_tokens = create_all_tokens(library_track.title, library_track.artist, library_track.album)

        # Get candidates from index
        candidate_ids = index.get_candidates(library_tokens, max_candidates=20)

        if not candidate_ids:
            continue

        # Score each candidate
        best_match = None
        best_score = 0.0

        for rb_track_id in candidate_ids:
            rb_track = index.get_track(rb_track_id)
            if rb_track is None:
                continue

            score = calculate_match_score(library_track, rb_track)

            if score > best_score:
                best_score = score
                best_match = rb_track

        # Update if match exceeds threshold
        if best_match and best_score >= min_confidence:
            logger.debug(
                f"Match: '{library_track.title}' by {library_track.artist} "
                f"→ '{best_match.title}' by {best_match.artist} "
                f"(confidence: {best_score:.2f})"
            )

            # Update LibraryTrack with Rekordbox metadata
            updates = {
                "in_rekordbox": True,
                "rekordbox_file_path": best_match.file_path,
                "rekordbox_bpm": best_match.bpm,
                "rekordbox_genre": best_match.genre,
                "rekordbox_key": best_match.key,
                "rekordbox_match_confidence": best_score,
            }
            # Update duration_ms if available and not already set
            if best_match.duration_ms and not library_track.duration_ms:
                updates["duration_ms"] = best_match.duration_ms
            
            db.update_track(library_track.id, updates)
            matched_count += 1
            updated_count += 1

    # Handle unmatched Rekordbox tracks (if --add-unmatched)
    if add_unmatched:
        logger.info("Processing unmatched Rekordbox tracks...")
        matched_rb_paths = {
            track.rekordbox_file_path
            for track in db.get_tracks_in_rekordbox()
            if track.rekordbox_file_path
        }

        for rb_track in rekordbox_tracks:
            if rb_track.file_path not in matched_rb_paths:
                # Create new LibraryTrack from Rekordbox track
                new_track = LibraryTrack(
                    title=rb_track.title,
                    artist=rb_track.artist,
                    album=rb_track.album,
                    duration_ms=rb_track.duration_ms,
                    in_rekordbox=True,
                    rekordbox_file_path=rb_track.file_path,
                    rekordbox_bpm=rb_track.bpm,
                    rekordbox_genre=rb_track.genre,
                    rekordbox_key=rb_track.key,
                    rekordbox_match_confidence=1.0,  # Direct import, perfect match
                )
                db.add_track(new_track)
                created_count += 1

    # Commit transaction
    db.commit()
    db.close()

    # Print summary
    logger.info("=" * 60)
    logger.info("Import Summary:")
    logger.info(f"  Rekordbox tracks parsed: {len(rekordbox_tracks)}")
    logger.info(f"  Library tracks processed: {len(library_tracks)}")
    logger.info(f"  Matched and updated: {updated_count}")
    logger.info(f"  Already in Rekordbox (skipped): {skipped_count}")
    if add_unmatched:
        logger.info(f"  New tracks created: {created_count}")
    logger.info("=" * 60)


def match_spotify(
    csv_path: Path,
    db_path: Path = Path("music.db"),
    rekordbox_tsv_path: Path | None = None,
    limit: int = 20,
    top_matches: int = 1,
    match_threshold: float = 90.0,
    exclude_matching: bool = False,
    with_amazon_links: bool = False,
    with_lucida_links: bool = False,
    sort_by_url_score: bool = False,
    sort_by_score: bool = False,
    spotify_id: str | None = None,
) -> None:
    """Match Spotify playlist tracks against Rekordbox collection.

    Args:
        csv_path: Path to Spotify playlist CSV file
        db_path: Path to SQLite database
        rekordbox_tsv_path: Optional path to Rekordbox TSV file (if not in DB)
        limit: Maximum number of Spotify tracks to process (default: 20)
        top_matches: Number of matches to display per track (default: 1)
        match_threshold: Score threshold for exclude-matching and display (default: 90.0)
        exclude_matching: Exclude tracks that have matches at or above match_threshold (default: False)
        with_amazon_links: Fetch Amazon Music links with caching (default: False)
        with_lucida_links: Show Lucida download links (cache only, no searches) (default: False)
        sort_by_url_score: Sort results by URL score (highest first) when using --with-amazon-links (default: False)
        sort_by_score: Sort results by match score (highest first) when not using link mode (default: False)
    """
    logger.info(f"Parsing Spotify playlist: {csv_path}")
    extractor = SpotifyPlaylistExtractor()
    spotify_tracks = extractor.parse_csv(csv_path)
    logger.info(f"Parsed {len(spotify_tracks)} Spotify tracks")
    
    # Filter to specific track if spotify_id provided
    if spotify_id:
        spotify_tracks = [t for t in spotify_tracks if t.spotify_id == spotify_id]
        if not spotify_tracks:
            logger.error(f"No track found with Spotify ID: {spotify_id}")
            sys.exit(1)
        logger.info(f"Debug mode: Matching single track with Spotify ID: {spotify_id}")
        limit = 1  # Override limit for debug mode

    # Load Rekordbox tracks from database (where rekordbox_file_path IS NOT NULL)
    db = LibraryDB(db_path)
    rekordbox_library_tracks = [
        track for track in db.get_all_tracks() if track.rekordbox_file_path
    ]
    logger.info(f"Found {len(rekordbox_library_tracks)} Rekordbox tracks in database")

    # If no Rekordbox tracks in DB, try to load from TSV
    if not rekordbox_library_tracks and rekordbox_tsv_path:
        logger.info(f"Loading Rekordbox tracks from TSV: {rekordbox_tsv_path}")
        rb_parser = RekordboxTSVParser()
        rekordbox_tsv_tracks = rb_parser.parse_tsv(rekordbox_tsv_path)
        logger.info(f"Parsed {len(rekordbox_tsv_tracks)} Rekordbox tracks from TSV")

        # Build index from TSV tracks
        logger.info("Building inverted index from TSV...")
        index = RekordboxIndex(rekordbox_tsv_tracks)
        index.build_index(rekordbox_tsv_tracks)
    else:
        # Build index from LibraryTracks
        logger.info("Building inverted index from database...")
        # Convert LibraryTracks to RekordboxTSVTrack-like objects for indexing
        rb_parser = RekordboxTSVParser()
        rekordbox_tsv_tracks = []
        for lib_track in rekordbox_library_tracks:
            # Create a RekordboxTSVTrack-like object from LibraryTrack
            from .rekordbox_tsv_parser import RekordboxTSVTrack
            rb_track = RekordboxTSVTrack(
                title=lib_track.title,
                artist=lib_track.artist,
                album=lib_track.album,
                genre=lib_track.rekordbox_genre,
                bpm=lib_track.rekordbox_bpm,
                key=lib_track.rekordbox_key,
                duration_ms=lib_track.duration_ms,
                file_path=lib_track.rekordbox_file_path or "",
            )
            rekordbox_tsv_tracks.append(rb_track)

        index = RekordboxIndex(rekordbox_tsv_tracks)
        index.build_index(rekordbox_tsv_tracks)

    logger.info(f"Index built: {len(index.tracks)} tracks, {len(index.token_index)} tokens")

    if with_lucida_links:
        logger.info("Lucida link display enabled (cache only, no searches)")
    elif with_amazon_links:
        logger.info("Amazon link fetching enabled (with caching)")
    else:
        logger.info("Amazon link fetching disabled")

    # Match each Spotify track (limit to first N tracks)
    # Updated tuple: (track_num, spotify_track, matches, amazon_url, amazon_price, amazon_page_title, from_cache, url_score)
    results: list[tuple[int, object, list[tuple[LibraryTrack, float]], str | None, str | None, str | None, bool, float]] = []
    total_tracks = len(spotify_tracks)
    tracks_to_process = spotify_tracks[:limit] if limit > 0 else spotify_tracks

    # Log processing start BEFORE the loop (so user knows what's happening during the delay)
    if total_tracks > limit:
        logger.info(f"Processing {len(tracks_to_process)} of {total_tracks} tracks (limit: {limit})...")
    else:
        logger.info(f"Processing {total_tracks} tracks...")

    for idx, spotify_track in enumerate(tracks_to_process, start=1):
        # Generate tokens from Spotify track (title + artist + album)
        spotify_tokens = create_all_tokens(
            spotify_track.title, spotify_track.artist, spotify_track.album
        )

        # Get candidates from index
        candidate_ids = index.get_candidates(spotify_tokens, max_candidates=50)

        # Fetch Amazon link if requested
        amazon_url: str | None = None
        amazon_price: str | None = None
        amazon_page_title: str | None = None
        from_cache = False
        
        if with_lucida_links:
            # Only check cache, no searches
            try:
                from .amazon_cache import AmazonCache, generate_cache_key
                
                cache = AmazonCache()
                cache_key = generate_cache_key(spotify_track.artist, spotify_track.title, spotify_track.album)
                cached_results = cache.get(cache_key)
                
                if cached_results is not None:
                    # Check if this is a "no results found" marker (empty list)
                    if len(cached_results) == 0:
                        # "No results" was cached - skip this track
                        pass
                    else:
                        # Filter out podcast URLs even from cache (same as amazon_service does)
                        valid_results = [
                            r for r in cached_results
                            if r.url and "/podcasts/" not in r.url.lower() and "/podcast/" not in r.url.lower()
                        ]
                        
                        if valid_results:
                            # Results are cached
                            from_cache = True
                            result = valid_results[0]
                            amazon_url = result.url
                            amazon_price = result.price
                            amazon_page_title = result.page_title
                            
                            # If page_title is missing, construct it from the search result title/artist
                            if not amazon_page_title:
                                if result.title and result.artist:
                                    amazon_page_title = f"{result.title} - {result.artist}"
                                elif result.title:
                                    amazon_page_title = result.title
                                elif result.artist:
                                    amazon_page_title = result.artist
                            logger.debug(f"Using cached Amazon link for Lucida: {spotify_track.title}")
            except Exception as e:
                logger.warning(f"Failed to get cached Amazon link for {spotify_track.title}: {e}")
        elif with_amazon_links:
            try:
                import time
                from .amazon_cache import AmazonCache, generate_cache_key
                
                # Check cache first before any delays
                cache = AmazonCache()
                cache_key = generate_cache_key(spotify_track.artist, spotify_track.title, spotify_track.album)
                cached_results = cache.get(cache_key)
                
                if cached_results is not None:
                    # Results are cached (either found or "no results" marker)
                    from_cache = True
                    if cached_results and cached_results[0].url:
                        result = cached_results[0]
                        amazon_url = result.url
                        amazon_price = result.price
                        amazon_page_title = result.page_title
                        
                        # If page_title is missing, construct it from the search result title/artist
                        if not amazon_page_title:
                            if result.title and result.artist:
                                amazon_page_title = f"{result.title} - {result.artist}"
                            elif result.title:
                                amazon_page_title = result.title
                            elif result.artist:
                                amazon_page_title = result.artist
                        logger.debug(f"Using cached Amazon link for {spotify_track.title}")
                else:
                    # Not in cache - need to search (with rate limiting)
                    # Rate limiting: 2 second delay between searches
                    if idx > 1:
                        time.sleep(2.0)
                    
                    search_results, _ = search_amazon_for_track(
                        artist=spotify_track.artist,
                        title=spotify_track.title,
                        album=spotify_track.album,
                        use_cache=True,
                        max_results=1,
                    )
                    
                    if search_results and search_results[0].url:
                        result = search_results[0]
                        amazon_url = result.url
                        amazon_price = result.price
                        amazon_page_title = result.page_title
                        
                        # If page_title is missing, construct it from the search result title/artist
                        if not amazon_page_title:
                            if result.title and result.artist:
                                amazon_page_title = f"{result.title} - {result.artist}"
                            elif result.title:
                                amazon_page_title = result.title
                            elif result.artist:
                                amazon_page_title = result.artist
                        
                        logger.info(f"Found Amazon link for {spotify_track.title} by {spotify_track.artist}")
            except Exception as e:
                logger.warning(f"Failed to search Amazon for {spotify_track.title}: {e}")

        # Calculate URL score if we have Amazon data (pass URL for track/album boost)
        # If we have a URL but no page_title, try to construct one from Spotify track info as fallback
        if amazon_url and not amazon_page_title:
            # Fallback: use Spotify track info to construct a page title for scoring
            amazon_page_title = f"{spotify_track.title} - {spotify_track.artist}"
        
        url_score = calculate_url_score(amazon_page_title, spotify_track.title, spotify_track.artist, amazon_url) if amazon_page_title else 0.0
        
        if not candidate_ids:
            # No matches found
            results.append((idx, spotify_track, [], amazon_url, amazon_price, amazon_page_title, from_cache, url_score))
            continue

        # Score each candidate
        matches: list[tuple[LibraryTrack, float]] = []

        for rb_track_id in candidate_ids:
            rb_track = index.get_track(rb_track_id)
            if rb_track is None:
                continue

            # Find corresponding LibraryTrack in database
            lib_track = None
            for lt in rekordbox_library_tracks:
                if lt.rekordbox_file_path == rb_track.file_path:
                    lib_track = lt
                    break

            # If not in DB, create a temporary LibraryTrack from RekordboxTSVTrack
            if lib_track is None:
                lib_track = LibraryTrack(
                    title=rb_track.title,
                    artist=rb_track.artist,
                    album=rb_track.album,
                    duration_ms=rb_track.duration_ms,
                    in_rekordbox=True,
                    rekordbox_file_path=rb_track.file_path,
                    rekordbox_bpm=rb_track.bpm,
                    rekordbox_genre=rb_track.genre,
                    rekordbox_key=rb_track.key,
                )

            # Create a temporary LibraryTrack from Spotify track for matching
            spotify_lib_track = LibraryTrack(
                title=spotify_track.title,
                artist=spotify_track.artist,
                album=spotify_track.album,
                duration_ms=spotify_track.duration_ms,
            )

            # Calculate match score (returns 0.0-1.0, convert to 0-100)
            # Note: calculate_match_score expects (library_track, rekordbox_track)
            # We're matching Spotify track (as LibraryTrack) against Rekordbox track
            score_0_1 = calculate_match_score(spotify_lib_track, rb_track)
            score_0_100 = score_0_1 * 100.0

            matches.append((lib_track, score_0_100))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        # If exclude_matching is True, skip tracks that have matches ≥ match_threshold
        if exclude_matching:
            has_good_match = any(score >= match_threshold for _, score in matches)
            if has_good_match:
                continue  # Skip this track

        # Keep top matches
        results.append((idx, spotify_track, matches, amazon_url, amazon_price, amazon_page_title, from_cache, url_score))
        
        # If debug mode, show debug output immediately and exit
        if spotify_id:
            print_match_debug(
                spotify_track,
                spotify_tokens,
                candidate_ids,
                matches,
                index,
                rekordbox_tsv_tracks,
            )
            return  # Exit early, don't show table

    # Sort results by URL score if requested (only when using --with-amazon-links or --with-lucida-links)
    if sort_by_url_score and (with_amazon_links or with_lucida_links):
        results.sort(key=lambda x: x[7], reverse=True)  # x[7] is url_score, sort descending
    # Sort results by match score if requested (only when not using link mode)
    elif sort_by_score and not (with_amazon_links or with_lucida_links):
        def best_match_score(result: tuple[int, object, list[tuple[LibraryTrack, float]], str | None, str | None, str | None, bool, float]) -> float:
            matches = result[2]
            if not matches:
                return 0.0
            return matches[0][1]
        results.sort(key=best_match_score, reverse=True)

    # Display results
    print()
    logger.info(f"Completed processing {len(results)} tracks")
    print()
    # Build header based on whether Amazon links or Lucida links are shown
    # Spotify Title: 32 (4/5 of 40), Spotify Artist: 24 (4/5 of 30)
    # URL column: ~87 characters (67 + 20)
    url_col_width = 87
    if with_lucida_links:
        print(f"{'#':<4} {'Spotify ID':<22} {'Spotify Title':<32} {'Spotify Artist':<24} {'URL Score':<10} {'Download Url':<{url_col_width}} {'Existing':<8}")
        print("-" * (4 + 22 + 32 + 24 + 10 + url_col_width + 8))
    elif with_amazon_links:
        print(f"{'#':<4} {'Spotify ID':<22} {'Spotify Title':<32} {'Spotify Artist':<24} {'URL Score':<10} {'Amazon URL':<{url_col_width}} {'Existing':<8}")
        print("-" * (4 + 22 + 32 + 24 + 10 + url_col_width + 8))
    else:
        threshold_label = f"≥{int(match_threshold)}" if match_threshold.is_integer() else f"≥{match_threshold:g}"
        print(f"{'#':<4} {'Spotify ID':<22} {'Spotify Title':<32} {'Spotify Artist':<24} {'Score':<8} {threshold_label:<5} {'Match Title':<40} {'Match Artist':<30} {'Filename':<50} {'Existing':<8}")
        print("-" * (4 + 22 + 32 + 24 + 8 + 5 + 40 + 30 + 50 + 8))

    for track_num, spotify_track, matches, amazon_url, amazon_price, amazon_page_title, from_cache, url_score in results:
        # Spotify Title: 32 chars, Artist: 24 chars (4/5 of original)
        title_display = spotify_track.title[:30] + ".." if len(spotify_track.title) > 32 else spotify_track.title
        artist_display = spotify_track.artist[:22] + ".." if len(spotify_track.artist) > 24 else spotify_track.artist
        spotify_id_display = spotify_track.spotify_id or "N/A"

        if not matches:
            # No matches
            if with_lucida_links or with_amazon_links:
                url_display = ""
                if amazon_url:
                    if with_lucida_links:
                        # Build Lucida download URL (no cache indicator, no page title)
                        lucida_url = f"https://lucida.to/?url={amazon_url}"
                        url_display = lucida_url
                    else:
                        # Show full Amazon URL with cache indicator and page title
                        cache_indicator = " (c)" if from_cache else ""
                        url_with_indicator = f"{amazon_url}{cache_indicator}"
                        
                        # Calculate available space for title (column width minus URL and separator)
                        available_space = url_col_width - len(url_with_indicator) - 3  # -3 for " | "
                        
                        if amazon_page_title:
                            # Show as much title as fits in the available column width
                            if len(amazon_page_title) <= available_space:
                                url_display = f"{url_with_indicator} | {amazon_page_title}"
                            else:
                                truncated_title = amazon_page_title[:available_space - 2] + ".."
                                url_display = f"{url_with_indicator} | {truncated_title}"
                        else:
                            url_display = f"{url_with_indicator} | null"
                else:
                    url_display = "Not found (no cached Amazon URL)" if with_lucida_links else "Not found"
                # Show URL score when showing links, otherwise show 0.0 for match score
                score_display = f"{url_score:>6.1f}" if (with_amazon_links or with_lucida_links) else "0.0"
                existing_display = "✅" if matches and any(score >= match_threshold for _, score in matches) else "❌"
                print(f"{track_num:<4} {spotify_id_display:<22} {title_display:<32} {artist_display:<24} {score_display:<10} {url_display:<{url_col_width}} {existing_display:<8}")
            else:
                print(f"{track_num:<4} {title_display:<32} {artist_display:<24} {'0.0':<8} {'0':<5} {'No match':<40} {'':<30} {'':<50} {'❌':<6}")
        else:
            # Count matches ≥ match_threshold
            matches_90_plus = sum(1 for _, score in matches if score >= match_threshold)
            best_match, best_score = matches[0]

            best_title = best_match.title[:38] + ".." if len(best_match.title) > 40 else best_match.title
            best_artist = best_match.artist[:28] + ".." if len(best_match.artist) > 30 else best_match.artist
            filename = best_match.rekordbox_file_path or ""
            if len(filename) > 48:
                filename = "..." + filename[-45:]

            status = "✅" if best_score >= match_threshold else "❌"
            existing_display = "✅" if best_score >= match_threshold else "❌"

            if with_lucida_links or with_amazon_links:
                # Format URL for display
                url_display = ""
                if amazon_url:
                    if with_lucida_links:
                        # Build Lucida download URL (no cache indicator, no page title)
                        lucida_url = f"https://lucida.to/?url={amazon_url}"
                        url_display = lucida_url
                    else:
                        # Show full Amazon URL with cache indicator and page title
                        cache_indicator = " (c)" if from_cache else ""
                        url_with_indicator = f"{amazon_url}{cache_indicator}"
                        
                        # Calculate available space for title (column width minus URL and separator)
                        available_space = url_col_width - len(url_with_indicator) - 3  # -3 for " | "
                        
                        if amazon_page_title:
                            # Show as much title as fits in the available column width
                            if len(amazon_page_title) <= available_space:
                                url_display = f"{url_with_indicator} | {amazon_page_title}"
                            else:
                                truncated_title = amazon_page_title[:available_space - 2] + ".."
                                url_display = f"{url_with_indicator} | {truncated_title}"
                        else:
                            url_display = f"{url_with_indicator} | null"
                else:
                    url_display = "Not found (no cached Amazon URL)" if with_lucida_links else "Not found"
                # Show URL score (not best_score) when showing links
                print(f"{track_num:<4} {spotify_id_display:<22} {title_display:<32} {artist_display:<24} {url_score:>6.1f}  {url_display:<{url_col_width}} {status:<6}")
            else:
                # Show best match
                print(f"{track_num:<4} {spotify_id_display:<22} {title_display:<32} {artist_display:<24} {best_score:>6.1f}  {matches_90_plus:<5} {best_title:<40} {best_artist:<30} {filename:<50} {existing_display:<8}")

                # Show additional matches if requested
                if top_matches > 1:
                    for extra_match, extra_score in matches[1:top_matches]:
                        extra_title = extra_match.title[:38] + ".." if len(extra_match.title) > 40 else extra_match.title
                        extra_artist = extra_match.artist[:28] + ".." if len(extra_match.artist) > 30 else extra_match.artist
                        extra_filename = extra_match.rekordbox_file_path or ""
                        if len(extra_filename) > 48:
                            extra_filename = "..." + extra_filename[-45:]
                        extra_status = "✅" if extra_score >= match_threshold else "❌"
                        print(f"{'':<4} {'':<22} {'':<32} {'':<24} {extra_score:>6.1f}  {'':<5} {extra_title:<40} {extra_artist:<30} {extra_filename:<50} {extra_status:<6}")

    print()
    db.close()


def get_amazon_link(artist: str, title: str) -> None:
    """Search Amazon Music for a track and display search queries and results.
    
    Uses the shared Amazon search service.
    
    Args:
        artist: Artist name
        title: Track title
    """
    # Use shared service
    search_results, queries = search_amazon_for_track(
        artist=artist,
        title=title,
        use_cache=True,
        max_results=10,
    )
    
    print(f"\nSearching for: {title} by {artist}\n")
    print("Search queries:")
    for i, query in enumerate(queries, 1):
        print(f"  {i}. {query}")
    print()
    
    if not search_results:
        print("No results found.")
        return
    
    # Show top 10 results (or all if less than 10)
    results_to_show = search_results[:10]
    
    print(f"Found {len(search_results)} result(s), showing top {len(results_to_show)}:\n")
    print(f"{'#':<4} {'URL Score':<12} {'Title':<40} {'Artist':<30} {'URL':<60}")
    print("-" * 146)
    
    # Calculate scores with details
    scored_results: list[tuple[AmazonSearchResult, float, dict[str, Any]]] = []
    for result in results_to_show:
        url_score, details = calculate_url_score(
            result.page_title, title, artist, result.url, return_details=True
        )
        scored_results.append((result, url_score, details))
    
    # Sort by URL score descending
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    for idx, (result, url_score, details) in enumerate(scored_results, 1):
        # Format URL for display
        url_display = result.url or "N/A"
        if len(url_display) > 58:
            url_display = url_display[:55] + "..."
        
        # Format title/artist for display
        title_display = result.title[:38] + ".." if len(result.title) > 40 else result.title
        artist_display = result.artist[:28] + ".." if len(result.artist) > 30 else result.artist
        
        print(f"{idx:<4} {url_score:>10.1f}  {title_display:<40} {artist_display:<30} {url_display:<60}")
        
        # Show token breakdown
        print(f"     Title tokens: {', '.join(details['title_tokens'])}")
        print(f"     Title scores: {', '.join(f'{k}:{v:.1f}' for k, v in details['title_token_scores'].items())}")
        print(f"     Artist tokens: {', '.join(details['artist_tokens'])}")
        artist_scores_str = []
        for token, score in details['artist_token_scores'].items():
            matched_token = details.get('artist_token_matches', {}).get(token)
            if matched_token:
                artist_scores_str.append(f'{token}:{score:.1f}(→{matched_token})')
            else:
                artist_scores_str.append(f'{token}:{score:.1f}(no match)')
        print(f"     Artist scores: {', '.join(artist_scores_str)}")
        print(f"     Amazon tokens: {', '.join(details['amazon_tokens'])}")
        print(f"     Title coverage: {details['title_coverage']:.2f}, Artist coverage: {details['artist_coverage']:.2f}")
        print(f"     Title score: {details['title_score']:.2f}, Artist score: {details['artist_score']:.2f}")
        if details.get('remix_penalty', 0) != 0:
            print(f"     Remix penalty: {details['remix_penalty']:.2f} (Amazon has remix/edit but Spotify doesn't)")
        if details.get('url_boost', 0) != 0:
            print(f"     URL boost: {details['url_boost']:.2f} (track URL)")
        print()
    
    # Show page titles if available
    print("Page titles:")
    for idx, (result, _, _) in enumerate(scored_results, 1):
        page_title = result.page_title or "N/A"
        print(f"  {idx}. {page_title}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="""Music collection management CLI for DJs.

Manage your music collection by importing tracks from Spotify playlists and Rekordbox,
matching them against your existing library, finding purchase links, and tracking downloads.

Commands:
  tracks list              Search and list tracks in the database
  match-spotify            Match Spotify playlist tracks against Rekordbox collection
  import-rekordbox         Import Rekordbox collection and match with existing tracks
  get-amazon-link          Search Amazon Music for a specific track
  mark-downloaded          Mark tracks as downloaded based on a file list

Examples:
  # Search for tracks
  mm tracks list --search "octave untold"
  
  # Match a Spotify playlist (CSV from chosic.com)
  mm match-spotify playlists/koko-groove.csv --with-amazon-links
  
  # Import Rekordbox collection
  mm import-rekordbox rekordbox/all-tracks.txt
  
  # Find Amazon link for a specific track
  mm get-amazon-link --artist "LF SYSTEM" --title "Your Love"
  
  # Mark downloaded files
  mm mark-downloaded downloads.txt

For detailed help on any command, use: mm <command> --help
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # tracks command
    tracks_parser = subparsers.add_parser("tracks", help="Track management commands")
    tracks_subparsers = tracks_parser.add_subparsers(dest="tracks_command", help="Track commands")

    # tracks list command
    list_parser = tracks_subparsers.add_parser("list", help="List/search tracks")
    list_parser.add_argument(
        "--search",
        type=str,
        help="Search query (matches across artist and title)",
    )
    list_parser.add_argument(
        "--match-duration",
        type=str,
        help="Match duration (MM:SS format, e.g., 4:58). Duration similarity is weighted 15%% in final score.",
    )
    list_parser.add_argument(
        "--db",
        type=Path,
        default=Path("music.db"),
        help="Path to SQLite database (default: music.db)",
    )
    list_parser.add_argument(
        "--threshold",
        type=float,
        default=60.0,
        help="Minimum match score (0-100, default: 60.0)",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results to return (default: 20)",
    )

    # match-spotify command
    match_parser = subparsers.add_parser(
        "match-spotify",
        help="Match Spotify playlist tracks against Rekordbox collection",
    )
    match_parser.add_argument(
        "csv_file",
        type=Path,
        help="Path to Spotify playlist CSV file",
    )
    match_parser.add_argument(
        "--db",
        type=Path,
        default=Path("music.db"),
        help="Path to SQLite database (default: music.db)",
    )
    match_parser.add_argument(
        "--rekordbox-tsv",
        type=Path,
        help="Optional path to Rekordbox TSV file (if Rekordbox tracks not in DB)",
    )
    match_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of Spotify tracks to process (default: 20)",
    )
    match_parser.add_argument(
        "--top",
        type=int,
        default=1,
        help="Number of matches to display per track (default: 1)",
    )
    match_parser.add_argument(
        "--exclude-matching",
        action="store_true",
        help="Exclude tracks that have matches with score ≥match-threshold (show only unmatched or low-score matches)",
    )
    match_parser.add_argument(
        "--match-threshold",
        type=float,
        default=90.0,
        help="Score threshold for exclude-matching and display (default: 90.0)",
    )
    match_parser.add_argument(
        "--with-amazon-links",
        action="store_true",
        help="Fetch Amazon Music links for tracks (uses cache to avoid duplicate searches)",
    )
    match_parser.add_argument(
        "--with-lucida-links",
        action="store_true",
        help="Show Lucida download links (cache only, no searches). Requires cached Amazon URLs.",
    )
    match_parser.add_argument(
        "--sort-by-url-score",
        action="store_true",
        help="Sort results by URL score (highest first) when using --with-amazon-links or --with-lucida-links",
    )
    match_parser.add_argument(
        "--sort-by-score",
        action="store_true",
        help="Sort results by match score (highest first) when not using --with-amazon-links or --with-lucida-links",
    )
    match_parser.add_argument(
        "--spotify-id",
        type=str,
        help="Debug mode: Match only this specific Spotify track ID and show detailed scoring",
    )

    # import-rekordbox command
    import_parser = subparsers.add_parser(
        "import-rekordbox",
        help="Import Rekordbox collection and match with existing tracks",
    )
    import_parser.add_argument(
        "tsv_file",
        type=Path,
        help="Path to Rekordbox TSV export file",
    )
    import_parser.add_argument(
        "--db",
        type=Path,
        default=Path("music.db"),
        help="Path to SQLite database (default: music.db)",
    )
    import_parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence score to update (0.0-1.0, default: 0.6)",
    )
    import_parser.add_argument(
        "--add-unmatched",
        action="store_true",
        help="Add unmatched Rekordbox tracks as new LibraryTracks",
    )

    # get-amazon-link command
    amazon_parser = subparsers.add_parser(
        "get-amazon-link",
        help="Search Amazon Music for a specific track and show search results",
    )
    amazon_parser.add_argument(
        "--artist",
        type=str,
        required=True,
        help="Artist name",
    )
    amazon_parser.add_argument(
        "--title",
        type=str,
        required=True,
        help="Track title",
    )

    # mark-downloaded command
    mark_parser = subparsers.add_parser(
        "mark-downloaded",
        help="Mark tracks as downloaded based on a file list",
    )
    mark_parser.add_argument(
        "file_list",
        type=Path,
        help="Path to text file with one filename per line",
    )
    mark_parser.add_argument(
        "--db",
        type=Path,
        default=Path("music.db"),
        help="Path to SQLite database (default: music.db)",
    )
    mark_parser.add_argument(
        "--threshold",
        type=float,
        default=85.0,
        help="Minimum match score (0-100, default: 85.0)",
    )

    args = parser.parse_args()

    if args.command == "tracks":
        if args.tracks_command == "list":
            if args.search:
                search_tracks(
                    db_path=args.db,
                    search_query=args.search,
                    threshold=args.threshold,
                    limit=args.limit,
                    match_duration=args.match_duration,
                )
            else:
                list_parser.print_help()
                sys.exit(1)
        else:
            tracks_parser.print_help()
            sys.exit(1)
    elif args.command == "match-spotify":
        if not args.csv_file.exists():
            logger.error(f"CSV file not found: {args.csv_file}")
            sys.exit(1)

        match_spotify(
            csv_path=args.csv_file,
            db_path=args.db,
            rekordbox_tsv_path=args.rekordbox_tsv,
            limit=args.limit,
            top_matches=args.top,
            match_threshold=args.match_threshold,
            exclude_matching=args.exclude_matching,
            with_amazon_links=args.with_amazon_links,
            with_lucida_links=args.with_lucida_links,
            sort_by_url_score=args.sort_by_url_score,
            sort_by_score=args.sort_by_score,
            spotify_id=args.spotify_id,
        )
    elif args.command == "import-rekordbox":
        if not args.tsv_file.exists():
            logger.error(f"TSV file not found: {args.tsv_file}")
            sys.exit(1)

        import_rekordbox(
            tsv_path=args.tsv_file,
            db_path=args.db,
            min_confidence=args.min_confidence,
            add_unmatched=args.add_unmatched,
        )
    elif args.command == "get-amazon-link":
        if not args.artist or not args.title:
            logger.error("Both --artist and --title are required")
            sys.exit(1)
        
        get_amazon_link(artist=args.artist, title=args.title)
    elif args.command == "mark-downloaded":
        if not args.file_list.exists():
            logger.error(f"File list not found: {args.file_list}")
            sys.exit(1)
        
        mark_downloaded(
            file_list_path=args.file_list,
            db_path=args.db,
            threshold=args.threshold,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
