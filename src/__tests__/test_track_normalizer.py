"""Tests for track normalization utilities."""

import pytest

from ..track_normalizer import (
    create_all_tokens,
    create_base_title,
    extract_artist_tokens,
    normalize_text,
    remove_junk_tokens,
    remove_label_tokens,
    standardize_feat_tokens,
    standardize_separators,
)


class TestNormalizeText:
    """Test normalize_text function."""

    def test_basic_normalization(self) -> None:
        """Test basic normalization."""
        assert normalize_text("Hello World") == "hello world"
        assert normalize_text("HELLO WORLD") == "hello world"

    def test_punctuation_removal(self) -> None:
        """Test punctuation removal."""
        assert normalize_text("Hello, World!") == "hello world"
        assert normalize_text("Showbiz (Edit)") == "showbiz edit"

    def test_whitespace_collapse(self) -> None:
        """Test whitespace collapsing."""
        assert normalize_text("Hello   World") == "hello world"
        assert normalize_text("Hello\tWorld") == "hello world"

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""

    def test_special_characters(self) -> None:
        """Test special character handling."""
        assert normalize_text("Track #1") == "track 1"
        assert normalize_text("A&B") == "a b"


class TestStandardizeFeatTokens:
    """Test standardize_feat_tokens function."""

    def test_feat_variations(self) -> None:
        """Test feat token standardization."""
        assert "feat" in standardize_feat_tokens("Artist feat. Guest")
        assert "feat" in standardize_feat_tokens("Artist ft Guest")
        assert "feat" in standardize_feat_tokens("Artist featuring Guest")

    def test_case_insensitive(self) -> None:
        """Test case insensitive matching."""
        assert "feat" in standardize_feat_tokens("Artist Feat Guest")
        assert "feat" in standardize_feat_tokens("Artist FT Guest")

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert standardize_feat_tokens("") == ""


class TestStandardizeSeparators:
    """Test standardize_separators function."""

    def test_ampersand(self) -> None:
        """Test ampersand normalization."""
        assert "and" in standardize_separators("Artist & Guest")
        assert "and" in standardize_separators("Artist&Guest")

    def test_comma(self) -> None:
        """Test comma normalization."""
        assert "and" in standardize_separators("Artist, Guest")
        assert "and" in standardize_separators("Artist,Guest")

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert standardize_separators("") == ""


class TestRemoveJunkTokens:
    """Test remove_junk_tokens function."""

    def test_junk_removal(self) -> None:
        """Test junk token removal."""
        assert "original" not in remove_junk_tokens("Track (Original Mix)")
        assert "mix" not in remove_junk_tokens("Track Original Mix")
        assert "edit" not in remove_junk_tokens("Track Radio Edit")
        assert "remix" not in remove_junk_tokens("Track Remix")
        assert "extended" not in remove_junk_tokens("Track Extended")

    def test_case_insensitive(self) -> None:
        """Test case insensitive removal."""
        assert "original" not in remove_junk_tokens("Track ORIGINAL MIX")
        assert "mix" not in remove_junk_tokens("Track Mix")

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert remove_junk_tokens("") == ""


class TestRemoveLabelTokens:
    """Test remove_label_tokens function."""

    def test_label_code_removal(self) -> None:
        """Test catalog code removal."""
        assert "KR006" not in remove_label_tokens("Track KR006")
        assert "ABC123" not in remove_label_tokens("Track ABC123")

    def test_preserve_non_labels(self) -> None:
        """Test that non-label codes are preserved."""
        result = remove_label_tokens("Track A1")
        assert "Track" in result or "track" in result

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert remove_label_tokens("") == ""


class TestExtractArtistTokens:
    """Test extract_artist_tokens function."""

    def test_feat_split(self) -> None:
        """Test splitting on feat."""
        tokens = extract_artist_tokens("Artist feat Guest")
        assert len(tokens) == 2
        assert "artist" in tokens
        assert "guest" in tokens

    def test_ampersand_split(self) -> None:
        """Test splitting on ampersand."""
        tokens = extract_artist_tokens("Artist & Guest")
        assert len(tokens) == 2

    def test_comma_split(self) -> None:
        """Test splitting on comma."""
        tokens = extract_artist_tokens("Artist, Guest")
        assert len(tokens) == 2

    def test_multiple_separators(self) -> None:
        """Test multiple separators."""
        tokens = extract_artist_tokens("Artist feat Guest & Another")
        assert len(tokens) >= 2

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert extract_artist_tokens("") == []

    def test_single_artist(self) -> None:
        """Test single artist."""
        tokens = extract_artist_tokens("Artist")
        assert len(tokens) == 1
        assert "artist" in tokens


class TestCreateBaseTitle:
    """Test create_base_title function."""

    def test_full_normalization(self) -> None:
        """Test full normalization pipeline."""
        title = "Showbiz Feat. Villa (Purple Disco Machine Edit)"
        base = create_base_title(title)
        # Should have junk removed
        assert "edit" not in base.lower()
        assert "showbiz" in base.lower()

    def test_label_removal(self) -> None:
        """Test label code removal."""
        title = "Track KR006"
        base = create_base_title(title)
        assert "kr006" not in base.lower()

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert create_base_title("") == ""


class TestCreateAllTokens:
    """Test create_all_tokens function."""

    def test_combined_tokens(self) -> None:
        """Test token combination."""
        tokens = create_all_tokens("Showbiz", "Yuksek")
        assert "showbiz" in tokens
        assert "yuksek" in tokens

    def test_deduplication(self) -> None:
        """Test token deduplication."""
        tokens = create_all_tokens("Artist Track", "Artist")
        # Should not have duplicate "artist"
        assert tokens.count("artist") == 1

    def test_empty_inputs(self) -> None:
        """Test empty input handling."""
        tokens = create_all_tokens("", "")
        assert isinstance(tokens, list)
