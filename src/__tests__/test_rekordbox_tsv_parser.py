"""Tests for Rekordbox TSV parser."""

import tempfile
from pathlib import Path

import pytest

from ..rekordbox_tsv_parser import (
    RekordboxTSVParser,
    RekordboxTSVTrack,
    parse_time_to_ms,
)


class TestParseTimeToMs:
    """Test parse_time_to_ms function."""

    def test_valid_time(self) -> None:
        """Test valid time conversion."""
        assert parse_time_to_ms("06:31") == 391000
        assert parse_time_to_ms("07:11") == 431000
        assert parse_time_to_ms("00:30") == 30000

    def test_invalid_time(self) -> None:
        """Test invalid time handling."""
        assert parse_time_to_ms("") is None
        assert parse_time_to_ms("invalid") is None
        assert parse_time_to_ms("6:31") is None  # Missing leading zero
        assert parse_time_to_ms("06:61") is None  # Invalid seconds

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert parse_time_to_ms("") is None
        assert parse_time_to_ms("   ") is None


class TestRekordboxTSVTrack:
    """Test RekordboxTSVTrack dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic track creation."""
        track = RekordboxTSVTrack(
            title="Test Track",
            artist="Test Artist",
            file_path="/path/to/track.mp3",
        )
        assert track.title == "Test Track"
        assert track.artist == "Test Artist"
        assert track.file_path == "/path/to/track.mp3"
        assert track.rb_track_id != ""

    def test_normalized_fields(self) -> None:
        """Test normalized fields are populated."""
        track = RekordboxTSVTrack(
            title="Showbiz Feat. Villa (Edit)",
            artist="Yuksek",
            file_path="/path/to/track.mp3",
        )
        assert track.base_title != ""
        assert track.full_title != ""
        assert len(track.artist_tokens) > 0
        assert len(track.all_tokens) > 0

    def test_id_generation(self) -> None:
        """Test ID generation."""
        track1 = RekordboxTSVTrack(
            title="Track", artist="Artist", file_path="/path/to/track.mp3"
        )
        track2 = RekordboxTSVTrack(
            title="Track", artist="Artist", file_path="/path/to/track.mp3"
        )
        # Same file path should generate same ID
        assert track1.rb_track_id == track2.rb_track_id

        # Different file path should generate different ID
        track3 = RekordboxTSVTrack(
            title="Track", artist="Artist", file_path="/different/path.mp3"
        )
        assert track1.rb_track_id != track3.rb_track_id


class TestRekordboxTSVParser:
    """Test RekordboxTSVParser class."""

    def test_parse_valid_tsv(self) -> None:
        """Test parsing valid TSV file."""
        # Create temporary TSV file
        tsv_content = """#	DJ Play Count	Rating	BPM	Key	Time	Color	Track Title	Artist	My Tag	Comments	Message	Genre	Album	Artwork	Location	Date Added
1	2	*****	135.00	1A	06:31		New Arrival	Zisko, ArchivOne		Visit https://ketrobinsonrecords.bandcamp.com			KR006		/path/to/track.mp3	2021-10-19
2	0	*****	118.00	Bbm	07:11		Showbiz Feat. Villa	Yuksek		Purchased at Beatport.com		Nu Disco / Disco	Showbiz		/path/to/track2.aiff	2021-08-15
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(tsv_content)
            temp_path = Path(f.name)

        try:
            parser = RekordboxTSVParser()
            tracks = parser.parse_tsv(temp_path)

            assert len(tracks) == 2
            assert tracks[0].title == "New Arrival"
            assert tracks[0].artist == "Zisko, ArchivOne"
            assert tracks[0].bpm == 135.00
            assert tracks[0].duration_ms == 391000
            assert tracks[0].file_path == "/path/to/track.mp3"

            assert tracks[1].title == "Showbiz Feat. Villa"
            assert tracks[1].artist == "Yuksek"
            assert tracks[1].duration_ms == 431000

        finally:
            temp_path.unlink()

    def test_skip_header(self) -> None:
        """Test header row is skipped."""
        tsv_content = """#	DJ Play Count	Rating	BPM	Key	Time	Color	Track Title	Artist	My Tag	Comments	Message	Genre	Album	Artwork	Location	Date Added
1	2	*****	135.00	1A	06:31		Test Track	Test Artist			Test		Test Genre	Test Album		/path/to/track.mp3	2021-10-19
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(tsv_content)
            temp_path = Path(f.name)

        try:
            parser = RekordboxTSVParser()
            tracks = parser.parse_tsv(temp_path)

            assert len(tracks) == 1
            assert tracks[0].title == "Test Track"

        finally:
            temp_path.unlink()

    def test_handle_missing_values(self) -> None:
        """Test handling of missing values."""
        tsv_content = """#	DJ Play Count	Rating	BPM	Key	Time	Color	Track Title	Artist	My Tag	Comments	Message	Genre	Album	Artwork	Location	Date Added
1	2	*****		1A			Test Track	Test Artist			Test		Test Genre		/path/to/track.mp3	2021-10-19
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(tsv_content)
            temp_path = Path(f.name)

        try:
            parser = RekordboxTSVParser()
            tracks = parser.parse_tsv(temp_path)

            assert len(tracks) == 1
            assert tracks[0].bpm is None
            assert tracks[0].duration_ms is None
            assert tracks[0].album is None

        finally:
            temp_path.unlink()

    def test_skip_invalid_rows(self) -> None:
        """Test invalid rows are skipped."""
        tsv_content = """#	DJ Play Count	Rating	BPM	Key	Time	Color	Track Title	Artist	My Tag	Comments	Message	Genre	Album	Artwork	Location	Date Added
1	2	*****	135.00	1A	06:31		Test Track	Test Artist			Test		Test Genre	Test Album		/path/to/track.mp3	2021-10-19
invalid row with not enough columns
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(tsv_content)
            temp_path = Path(f.name)

        try:
            parser = RekordboxTSVParser()
            tracks = parser.parse_tsv(temp_path)

            # Should only parse valid row
            assert len(tracks) == 1

        finally:
            temp_path.unlink()

    def test_file_not_found(self) -> None:
        """Test file not found error."""
        parser = RekordboxTSVParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_tsv("/nonexistent/file.txt")
