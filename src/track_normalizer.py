"""Text normalization utilities for track matching.

Provides functions to normalize track titles, artist names, and extract tokens
for fuzzy matching and indexing.
"""

import re
from typing import Any


def normalize_text(text: str) -> str:
    """Base normalization: lowercase, strip punctuation, collapse whitespace.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return ""
    # 1. Lowercase
    text = text.lower()
    # 2. Remove punctuation (keep alphanumeric and spaces)
    text = re.sub(r"[^\w\s]", " ", text)
    # 3. Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # 4. Strip
    return text.strip()


def standardize_feat_tokens(text: str) -> str:
    """Normalize feat/ft/featuring variations.

    Args:
        text: Input text

    Returns:
        Text with feat tokens standardized
    """
    if not text:
        return ""
    # Replace all variations with "feat"
    text = re.sub(r"\b(feat|ft|featuring)\b", "feat", text, flags=re.IGNORECASE)
    return text


def standardize_separators(text: str) -> str:
    """Normalize &/and/, separators.

    Args:
        text: Input text

    Returns:
        Text with separators standardized
    """
    if not text:
        return ""
    # Replace & and , with "and"
    text = re.sub(r"\s*&\s*", " and ", text)
    text = re.sub(r"\s*,\s*", " and ", text)
    return text


def remove_junk_tokens(text: str) -> str:
    """Remove common junk tokens from titles.

    Args:
        text: Input text

    Returns:
        Text with junk tokens removed
    """
    if not text:
        return ""
    junk_patterns = [
        r"\boriginal mix\b",
        r"\bextended\b",
        r"\bradio edit\b",
        r"\bedit\b",
        r"\bmix\b",
        r"\bremix\b",
        r"\bversion\b",
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return normalize_text(text)  # Re-normalize after removal


def remove_label_tokens(text: str) -> str:
    r"""Remove catalog codes like KR006, [A-Z]{2,}\d+.

    Args:
        text: Input text

    Returns:
        Text with label tokens removed
    """
    if not text:
        return ""
    # Remove catalog codes (2+ uppercase letters followed by digits)
    text = re.sub(r"\b[A-Z]{2,}\d+\b", "", text)
    return normalize_text(text)


def extract_artist_tokens(artist: str) -> list[str]:
    """Split artist string on feat/&/, and normalize each token.

    Args:
        artist: Artist name string

    Returns:
        List of normalized artist tokens
    """
    if not artist:
        return []
    # First standardize separators
    artist = standardize_separators(artist)
    # Split on "feat" or "and"
    tokens = re.split(r"\s+feat\s+|\s+and\s+", artist, flags=re.IGNORECASE)
    # Normalize each token
    return [normalize_text(token) for token in tokens if token.strip()]


def create_base_title(title: str) -> str:
    """Apply all normalization + remove junk/label tokens.

    Args:
        title: Track title

    Returns:
        Base title with junk and label tokens removed
    """
    if not title:
        return ""
    # Apply all normalization steps
    text = standardize_feat_tokens(title)
    text = standardize_separators(text)
    text = remove_junk_tokens(text)
    text = remove_label_tokens(text)
    return text


def create_all_tokens(title: str, artist: str) -> list[str]:
    """Combine base_title tokens + artist_tokens.

    Args:
        title: Track title
        artist: Artist name

    Returns:
        Combined list of normalized tokens
    """
    base_title = create_base_title(title)
    artist_tokens = extract_artist_tokens(artist)

    # Split base_title into tokens
    title_tokens = [token for token in base_title.split() if token]

    # Combine and deduplicate
    all_tokens = list(set(title_tokens + artist_tokens))
    return all_tokens
