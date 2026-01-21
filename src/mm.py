"""Main CLI tool for music collection management.

Commands:
    mm import-rekordbox <tsv_file>  - Import Rekordbox collection and match with existing tracks
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rapidfuzz import fuzz

from .library_db import LibraryDB, LibraryTrack
from .rekordbox_index import RekordboxIndex
from .rekordbox_tsv_parser import RekordboxTSVParser
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


def calculate_match_score(
    library_track: LibraryTrack, rekordbox_track, duration_hint: bool = True
) -> float:
    """Calculate match score between LibraryTrack and RekordboxTSVTrack.

    Args:
        library_track: LibraryTrack from database
        rekordbox_track: RekordboxTSVTrack from TSV
        duration_hint: Whether to use duration as a hint (default: True)

    Returns:
        Confidence score 0.0-1.0
    """
    # Normalize LibraryTrack fields using track_normalizer for consistency
    library_title_normalized = normalize_text(library_track.title)
    library_title_base = create_base_title(library_track.title)
    library_artist_normalized = normalize_text(library_track.artist)

    # Title similarity (normalized titles)
    title_score = fuzz.token_sort_ratio(
        library_title_normalized, rekordbox_track.full_title
    ) / 100.0

    # Artist similarity (compare with all artist tokens)
    artist_scores = []
    for rb_artist_token in rekordbox_track.artist_tokens:
        score = fuzz.ratio(library_artist_normalized, rb_artist_token) / 100.0
        artist_scores.append(score)
    artist_score = max(artist_scores) if artist_scores else 0.0

    # Swap score (handle metadata swaps - artist in title, title in artist)
    swap_title_score = fuzz.token_sort_ratio(
        library_title_normalized, " ".join(rekordbox_track.artist_tokens)
    ) / 100.0
    swap_artist_score = fuzz.ratio(
        library_artist_normalized, rekordbox_track.base_title
    ) / 100.0
    swap_score = max(swap_title_score, swap_artist_score)

    # Use best of normal vs swapped
    title_final = max(title_score, swap_score)
    artist_final = max(artist_score, swap_score)

    # Combined text similarity (weighted)
    text_score = (title_final * 0.7) + (artist_final * 0.25)

    # Duration hint (if both have duration)
    duration_boost = 0.0
    if duration_hint and library_track.duration_ms and rekordbox_track.duration_ms:
        duration_diff = abs(library_track.duration_ms - rekordbox_track.duration_ms)
        if duration_diff < 10000:  # < 10 seconds
            duration_boost = 0.05
        elif duration_diff < 30000:  # < 30 seconds
            duration_boost = 0.02
        elif duration_diff > 90000:  # > 90 seconds
            duration_boost = -0.05

    # Final score
    confidence = min(1.0, max(0.0, text_score + duration_boost))

    return confidence


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
        library_tokens = create_all_tokens(library_track.title, library_track.artist)

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


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Music collection management CLI",
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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
