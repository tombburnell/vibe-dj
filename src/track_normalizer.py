"""Text normalization utilities for track matching.

Provides functions to normalize track titles, artist names, and extract tokens
for fuzzy matching and indexing.
"""

import re
from typing import Any, Optional


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
    """Remove common junk tokens from titles that are not identifiers.

    Junk tokens are metadata/service words like "beatport", "spotify", "downloaded"
    that don't help identify the track. Mix/remix/edit/version and catalog codes
    are kept as they are identifiers.

    Args:
        text: Input text

    Returns:
        Text with junk tokens removed
    """
    if not text:
        return ""
    junk_patterns = [
        r"\bbeatport\b",
        r"\bspotify\b",
        r"\bdownloaded\b",
        r"\bdownload\b",
        r"\bimported\b",
        r"\bimport\b",
        r"\bfrom\b",
        r"\bthe\b",  # Common article, not an identifier
        r"\ba\b",  # Common article
        r"\ban\b",  # Common article
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return normalize_text(text)  # Re-normalize after removal


def remove_label_tokens(text: str) -> str:
    """Label tokens are now kept as identifiers - this function is deprecated.
    
    Catalog codes like KR006 are identifiers, not junk.
    This function now just returns normalized text for backward compatibility.

    Args:
        text: Input text

    Returns:
        Normalized text (no tokens removed)
    """
    if not text:
        return ""
    # Keep catalog codes - they're identifiers
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
    """Apply normalization + remove only actual junk tokens.

    Keeps mix/remix/edit/version and catalog codes as they are identifiers.
    Only removes service/metadata words like "beatport", "spotify", "downloaded".

    Args:
        title: Track title

    Returns:
        Base title with only junk tokens removed (identifiers preserved)
    """
    if not title:
        return ""
    # Apply normalization steps
    text = standardize_feat_tokens(title)
    text = standardize_separators(text)
    text = remove_junk_tokens(text)  # Only removes actual junk, not identifiers
    # Note: remove_label_tokens is now a no-op (catalog codes are identifiers)
    text = remove_label_tokens(text)  # Still called for backward compatibility
    return text


def create_all_tokens(title: str, artist: str, album: Optional[str] = None) -> list[str]:
    """Combine base_title tokens + artist_tokens + album_tokens.

    Args:
        title: Track title
        artist: Artist name
        album: Album name (optional)

    Returns:
        Combined list of normalized tokens
    """
    base_title = create_base_title(title)
    artist_tokens = extract_artist_tokens(artist)

    # Split base_title into tokens
    title_tokens = [token for token in base_title.split() if token]

    # Add album tokens if provided
    album_tokens: list[str] = []
    if album:
        # Normalize album (remove junk but keep mix/remix/edit/version and catalog codes)
        album_normalized = create_base_title(album)
        album_tokens = [token for token in album_normalized.split() if token]

    # Combine and deduplicate
    all_tokens = list(set(title_tokens + artist_tokens + album_tokens))
    return all_tokens
