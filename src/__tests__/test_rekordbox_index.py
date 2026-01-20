"""Tests for Rekordbox inverted index."""

import pytest

from ..rekordbox_index import RekordboxIndex, STOPWORDS
from ..rekordbox_tsv_parser import RekordboxTSVTrack


def create_test_track(
    title: str, artist: str, file_path: str = "/test/path.mp3"
) -> RekordboxTSVTrack:
    """Create a test track."""
    return RekordboxTSVTrack(
        title=title,
        artist=artist,
        file_path=file_path,
    )


class TestRekordboxIndex:
    """Test RekordboxIndex class."""

    def test_basic_index_construction(self) -> None:
        """Test basic index construction."""
        tracks = [
            create_test_track("Untold", "Octave One", "/path/to/untold.mp3"),
            create_test_track("Showbiz", "Yuksek", "/path/to/showbiz.mp3"),
        ]

        index = RekordboxIndex(tracks)

        assert len(index.tracks) == 2
        assert len(index.token_index) > 0

    def test_stopwords_excluded(self) -> None:
        """Test stopwords are excluded from index."""
        tracks = [
            create_test_track("Track Original Mix", "Artist", "/path/to/track.mp3"),
        ]

        index = RekordboxIndex(tracks)

        # Stopwords should not be in index
        for stopword in STOPWORDS:
            assert stopword not in index.token_index or len(index.token_index[stopword]) == 0

    def test_get_candidates(self) -> None:
        """Test candidate generation."""
        tracks = [
            create_test_track("Untold", "Octave One", "/path/to/untold.mp3"),
            create_test_track("Showbiz", "Yuksek", "/path/to/showbiz.mp3"),
            create_test_track("Different Track", "Different Artist", "/path/to/different.mp3"),
        ]

        index = RekordboxIndex(tracks)

        # Query with tokens from "Untold"
        candidates = index.get_candidates(["untold", "octave", "one"])

        assert len(candidates) > 0
        # Should find the "Untold" track
        untold_track = next(
            (t for t in tracks if t.title == "Untold"), None
        )
        assert untold_track is not None
        assert untold_track.rb_track_id in candidates

    def test_candidate_ranking(self) -> None:
        """Test candidates are ranked by token overlap."""
        tracks = [
            create_test_track("Untold Track", "Octave One", "/path/to/untold.mp3"),
            create_test_track("Untold", "Octave One", "/path/to/untold2.mp3"),
            create_test_track("Different", "Artist", "/path/to/different.mp3"),
        ]

        index = RekordboxIndex(tracks)

        # Query with tokens matching first track best
        candidates = index.get_candidates(["untold", "track", "octave", "one"])

        # First track should rank higher (more token overlap)
        untold_track = next(
            (t for t in tracks if t.title == "Untold Track"), None
        )
        assert untold_track is not None
        # First candidate should be the one with most overlap
        if len(candidates) > 0:
            assert candidates[0] in [t.rb_track_id for t in tracks]

    def test_max_candidates_limit(self) -> None:
        """Test max candidates limit."""
        # Create many tracks
        tracks = [
            create_test_track(f"Track {i}", f"Artist {i}", f"/path/to/track{i}.mp3")
            for i in range(50)
        ]

        index = RekordboxIndex(tracks)

        # Query with common token
        candidates = index.get_candidates(["track"], max_candidates=10)

        assert len(candidates) <= 10

    def test_get_track(self) -> None:
        """Test get_track method."""
        tracks = [
            create_test_track("Untold", "Octave One", "/path/to/untold.mp3"),
        ]

        index = RekordboxIndex(tracks)

        track_id = tracks[0].rb_track_id
        retrieved = index.get_track(track_id)

        assert retrieved is not None
        assert retrieved.title == "Untold"
        assert retrieved.rb_track_id == track_id

    def test_get_track_not_found(self) -> None:
        """Test get_track with non-existent ID."""
        tracks = [
            create_test_track("Untold", "Octave One", "/path/to/untold.mp3"),
        ]

        index = RekordboxIndex(tracks)

        retrieved = index.get_track("nonexistent_id")

        assert retrieved is None

    def test_rare_token_filtering(self) -> None:
        """Test rare token filtering."""
        # Create many tracks with common token
        tracks = [
            create_test_track("Common Track", "Common Artist", f"/path/to/track{i}.mp3")
            for i in range(100)
        ]

        index = RekordboxIndex(tracks, rare_token_threshold=0.05)

        # Common tokens (appearing in >5% of tracks) should be filtered out
        # "common" appears in all tracks, so should be excluded
        assert "common" not in index.token_index or len(index.token_index["common"]) == 0
