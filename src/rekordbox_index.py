"""Inverted index for fast Rekordbox track candidate generation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .rekordbox_tsv_parser import RekordboxTSVTrack

logger = logging.getLogger(__name__)

# Stopwords excluded from index (too frequent to be useful)
STOPWORDS = {
    "track",
    "mix",
    "original",
    "edit",
    "remix",
    "version",
    "extended",
    "radio",
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "feat",
    "ft",
    "featuring",
}


class RekordboxIndex:
    """Inverted index for Rekordbox tracks."""

    def __init__(self, tracks: list[RekordboxTSVTrack]) -> None:
        """Initialize index.

        Args:
            tracks: List of Rekordbox tracks to index
        """
        # Inverted index: token -> set[rb_track_id]
        self.token_index: dict[str, set[str]] = {}

        # Forward index: rb_track_id -> RekordboxTSVTrack
        self.tracks: dict[str, RekordboxTSVTrack] = {}

        # Token frequency: token -> count (for rare token filtering)
        self.token_frequency: dict[str, int] = {}

        # Total tracks (for frequency calculations)
        self.total_tracks: int = len(tracks)

        # Build index
        self.build_index(tracks)

    def build_index(
        self, tracks: list[RekordboxTSVTrack], rare_token_threshold: float = 0.05
    ) -> None:
        """Build inverted index from Rekordbox tracks.

        Args:
            tracks: List of Rekordbox tracks to index
            rare_token_threshold: Only index tokens appearing in < threshold% of tracks
        """
        # Step 1: Count token frequencies
        for track in tracks:
            for token in track.all_tokens:
                self.token_frequency[token] = self.token_frequency.get(token, 0) + 1

        # Step 2: Build index with rare tokens only
        # For very small libraries, int(N * threshold) can be 0 and would index nothing.
        max_frequency = max(1, int(self.total_tracks * rare_token_threshold))

        for track in tracks:
            self.tracks[track.rb_track_id] = track

            for token in track.all_tokens:
                # Only index rare tokens (exclude stopwords and common tokens)
                if (
                    self.token_frequency[token] <= max_frequency
                    and token not in STOPWORDS
                ):
                    if token not in self.token_index:
                        self.token_index[token] = set()
                    self.token_index[token].add(track.rb_track_id)

        logger.info(
            f"Built index: {len(self.tracks)} tracks, "
            f"{len(self.token_index)} tokens indexed"
        )

    def get_candidates(
        self, spotify_tokens: list[str], max_candidates: int = 100
    ) -> list[str]:
        """Generate candidate Rekordbox track IDs from Spotify track tokens.

        Args:
            spotify_tokens: Normalized tokens from Spotify track
            max_candidates: Maximum number of candidates to return

        Returns:
            List of rb_track_id sorted by token overlap count
        """
        # Step 1: Union candidate sets from token index
        candidate_scores: dict[str, int] = {}  # rb_track_id -> overlap count

        for token in spotify_tokens:
            if token in self.token_index:
                for rb_track_id in self.token_index[token]:
                    candidate_scores[rb_track_id] = (
                        candidate_scores.get(rb_track_id, 0) + 1
                    )

        # Step 2: Sort by overlap count (descending)
        sorted_candidates = sorted(
            candidate_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Step 3: Return top candidates
        return [rb_track_id for rb_track_id, _ in sorted_candidates[:max_candidates]]

    def get_track(self, rb_track_id: str) -> RekordboxTSVTrack | None:
        """Get track by ID.

        Args:
            rb_track_id: Track ID

        Returns:
            RekordboxTSVTrack or None if not found
        """
        return self.tracks.get(rb_track_id)
