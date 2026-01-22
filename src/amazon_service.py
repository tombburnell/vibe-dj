"""Amazon Music search service.

Provides shared Amazon search functionality for CLI commands.
"""

from __future__ import annotations

import logging
from typing import Any

from .amazon_cache import AmazonCache, generate_cache_key
from .amazon_music import AmazonMusicSearcher, AmazonSearchResult
from .spotify_client import Track
from .track_normalizer import create_all_tokens

logger = logging.getLogger(__name__)


def compress_token_similarity_score(
    raw_score: float,
    token1_length: int,
    token2_length: int,
    short_word_threshold: int = 4,
    short_word_power: float = 3.0,
    long_word_power: float = 2.5,
) -> float:
    """Apply length-based power transform to compress token similarity scores.
    
    Shorter words are more prone to false matches due to fewer characters,
    so they get more aggressive compression (higher power). Longer words get
    moderate compression to preserve meaningful similarity signals.
    
    Args:
        raw_score: Raw similarity score from fuzzy matching (0.0-1.0)
        token1_length: Length of first token
        token2_length: Length of second token
        short_word_threshold: Characters threshold for "short" words (default: 4)
        short_word_power: Power exponent for short words (default: 3.0)
        long_word_power: Power exponent for longer words (default: 2.5)
        
    Returns:
        Compressed similarity score (0.0-1.0)
        
    Examples:
        >>> compress_token_similarity_score(0.4, 2, 4)  # Short word match
        0.064  # 0.4^3.0
        >>> compress_token_similarity_score(0.4, 6, 7)  # Long word match
        0.101  # 0.4^2.5
        >>> compress_token_similarity_score(1.0, 2, 2)  # Perfect match
        1.0  # Always 1.0 regardless of power
    """
    min_length = min(token1_length, token2_length)
    
    if min_length <= short_word_threshold:
        power = short_word_power
    else:
        power = long_word_power
    
    return raw_score ** power


def calculate_token_match_score(
    spotify_token: str,
    amazon_tokens: list[str],
    compress_scores: bool = True,
) -> tuple[float, str | None]:
    """Calculate best match score for a Spotify token against Amazon tokens.
    
    Uses fuzzy matching to find the best matching Amazon token, optionally
    applying length-based compression to reduce false positives.
    
    Args:
        spotify_token: Token from Spotify (title or artist)
        amazon_tokens: List of tokens from Amazon title to match against
        compress_scores: Whether to apply length-based power compression (default: True)
        
    Returns:
        Tuple of (best_match_score, best_matching_amazon_token)
        Score is 0.0-1.0, token is None if no match found
    """
    from rapidfuzz import fuzz
    
    best_match = 0.0
    best_amazon_token = None
    
    for amazon_token in amazon_tokens:
        raw_score = fuzz.ratio(spotify_token, amazon_token) / 100.0
        
        if compress_scores:
            score = compress_token_similarity_score(
                raw_score,
                len(spotify_token),
                len(amazon_token),
            )
        else:
            score = raw_score
        
        if score > best_match:
            best_match = score
            best_amazon_token = amazon_token
    
    return (best_match, best_amazon_token)


def search_amazon_for_track(
    artist: str,
    title: str,
    album: str | None = None,
    use_cache: bool = True,
    max_results: int = 10,
) -> tuple[list[AmazonSearchResult], list[str]]:
    """Search Amazon Music for a track and return results with search queries.
    
    This is the shared service function used by both match-spotify and get-amazon-link.
    
    Args:
        artist: Artist name
        title: Track title
        album: Album name (optional)
        use_cache: Whether to use cache for results
        max_results: Maximum number of results to return
        
    Returns:
        Tuple of (list of search results, list of search queries used)
    """
    # Create a Track object for searching
    track = Track(title=title, artist=artist, album=album)
    
    # Build the queries that will be used (same as in AmazonMusicSearcher)
    queries = [
        f'site:music.amazon.com "{title}" "{artist}"',
        f'site:music.amazon.com "{title}"',
        f'site:music.amazon.com "{artist}" "{title}"',
        f'site:amazon.com "{title}" "{artist}" digital music',
    ]
    
    # Initialize searcher
    searcher = AmazonMusicSearcher(use_duckduckgo=True)
    
    # Check cache if enabled
    cached_results: list[AmazonSearchResult] | None = None
    if use_cache:
        cache = AmazonCache()
        cache_key = generate_cache_key(artist, title, album)
        cached_results = cache.get(cache_key)
        
        if cached_results is not None:
            # Check if this is a "no results found" marker (empty list)
            if len(cached_results) == 0:
                logger.debug(f"Using cached 'no results' for {title} by {artist}")
                return ([], queries)
            
            # Filter out podcast URLs even from cache
            valid_results = [
                r for r in cached_results
                if r.url and "/podcasts/" not in r.url.lower() and "/podcast/" not in r.url.lower()
            ]
            if valid_results:
                logger.debug(f"Using cached Amazon results for {title}")
                return (valid_results[:max_results], queries)
    
    # Perform the search
    try:
        search_results = searcher.search_track(track)
        
        # Filter out podcast URLs from fresh search results
        if search_results:
            search_results = [
                r for r in search_results
                if r.url and "/podcasts/" not in r.url.lower() and "/podcast/" not in r.url.lower()
            ]
        
        # Cache results if enabled (including empty results to mark "no results found")
        if use_cache:
            cache = AmazonCache()
            cache_key = generate_cache_key(artist, title, album)
            # Cache empty list to mark "no results found" so we don't search again
            cache.set(cache_key, search_results if search_results else [])
            cache.save()
        
        return (search_results[:max_results] if search_results else [], queries)
    except Exception as e:
        logger.error(f"Failed to search Amazon for {title} by {artist}: {e}")
        # Don't cache errors - let them retry next time
        return ([], queries)


def calculate_url_score(
    amazon_title: str | None,
    spotify_title: str,
    spotify_artist: str,
    amazon_url: str | None = None,
    return_details: bool = False,
) -> float | tuple[float, dict[str, Any]]:
    """Calculate URL score by comparing tokens from Amazon title vs Spotify title + artist.
    
    Similar to calculate_match_score for Rekordbox matching:
    - Compares title tokens separately from artist tokens
    - Gives higher weight to results containing both title and artist
    - Boosts /tracks URLs over /albums URLs
    - Penalizes remixes/edits if original title doesn't have them
    
    Args:
        amazon_title: Title from DuckDuckGo/Amazon search result
        spotify_title: Track title from Spotify
        spotify_artist: Artist name from Spotify
        amazon_url: Amazon URL (optional, for track/album boost)
        return_details: If True, return tuple of (score, details dict)
        
    Returns:
        Score from 0-100, or tuple of (score, details) if return_details=True
    """
    if not amazon_title:
        if return_details:
            return (0.0, {"error": "No Amazon title"})
        return 0.0
    
    from rapidfuzz import fuzz
    from .track_normalizer import (
        create_base_title,
        extract_artist_tokens,
        normalize_text,
    )
    
    # Extract tokens from Spotify (separate title and artist)
    spotify_title_base = create_base_title(spotify_title)
    spotify_title_tokens_list = [t for t in spotify_title_base.split() if t]
    spotify_title_tokens = set(spotify_title_tokens_list)
    
    # Extract artist tokens - split multi-word tokens into individual words for matching
    spotify_artist_tokens_list_raw = extract_artist_tokens(spotify_artist)
    spotify_artist_tokens_list = []
    for artist_token in spotify_artist_tokens_list_raw:
        # Split multi-word artist tokens into individual words
        words = artist_token.split()
        spotify_artist_tokens_list.extend(words)
    spotify_artist_tokens = set(spotify_artist_tokens_list)
    
    # Extract tokens from Amazon title
    amazon_title_base = create_base_title(amazon_title)
    amazon_tokens_list = [t for t in amazon_title_base.split() if t]
    amazon_tokens = set(amazon_tokens_list)
    
    if not spotify_title_tokens and not spotify_artist_tokens:
        if return_details:
            return (0.0, {"error": "No Spotify tokens"})
        return 0.0
    
    # Calculate token-by-token scores for title using shared function
    title_token_scores: dict[str, float] = {}
    for token in spotify_title_tokens_list:
        score, _ = calculate_token_match_score(token, amazon_tokens_list, compress_scores=True)
        title_token_scores[token] = score
    
    # Calculate token-by-token scores for artist using shared function
    artist_token_scores: dict[str, float] = {}
    artist_token_matches: dict[str, str | None] = {}  # Track which Amazon token matched
    for token in spotify_artist_tokens_list:
        score, matched_token = calculate_token_match_score(token, amazon_tokens_list, compress_scores=True)
        artist_token_scores[token] = score
        artist_token_matches[token] = matched_token
    
    # Title matching: coverage and average token score
    title_common = spotify_title_tokens & amazon_tokens
    title_coverage = (
        len(title_common) / len(spotify_title_tokens)
        if spotify_title_tokens
        else 0.0
    )
    title_avg_token_score = (
        sum(title_token_scores.values()) / len(title_token_scores)
        if title_token_scores
        else 0.0
    )
    
    # Artist matching: coverage and average token score
    # Count tokens that have a good match (>= 0.8) for coverage
    artist_matched_tokens = sum(1 for score in artist_token_scores.values() if score >= 0.8)
    artist_coverage = (
        artist_matched_tokens / len(spotify_artist_tokens_list)
        if spotify_artist_tokens_list
        else 0.0
    )
    artist_avg_token_score = (
        sum(artist_token_scores.values()) / len(artist_token_scores)
        if artist_token_scores
        else 0.0
    )
    
    # Also use fuzzy matching for quality (similar to calculate_match_score)
    # Title similarity
    spotify_title_normalized = normalize_text(spotify_title)
    amazon_title_normalized = normalize_text(amazon_title)
    title_fuzzy = fuzz.token_sort_ratio(
        spotify_title_normalized, amazon_title_normalized
    ) / 100.0
    
    # Artist similarity (check if any artist token appears in Amazon title)
    artist_fuzzy = 0.0
    if spotify_artist_tokens:
        artist_scores = []
        for artist_token in spotify_artist_tokens:
            # Check if artist token appears in Amazon title (fuzzy)
            best_score = 0.0
            for amazon_token in amazon_tokens:
                score = fuzz.ratio(artist_token, amazon_token) / 100.0
                if score > best_score:
                    best_score = score
            artist_scores.append(best_score)
        artist_fuzzy = max(artist_scores) if artist_scores else 0.0
    
    # Combined title score: coverage + token scores + fuzzy (weighted)
    title_score = (title_coverage * 0.4 + title_avg_token_score * 0.4 + title_fuzzy * 0.2)
    
    # Combined artist score: coverage + token scores + fuzzy (weighted)
    artist_score = (artist_coverage * 0.4 + artist_avg_token_score * 0.4 + artist_fuzzy * 0.2)
    
    # Weighted combination: artist 70%, title 30% (artist is more distinctive/important)
    # Multiple tracks can have the same name by different artists, so artist match is critical
    text_score = (artist_score * 0.7) + (title_score * 0.3)
    
    # Artist match threshold - require minimum artist match quality
    # If artist doesn't match well, heavily penalize the score
    artist_match_threshold = 0.5  # Require at least 50% artist match
    artist_penalty = 0.0
    if artist_score < artist_match_threshold:
        # Heavy penalty for weak artist matches (e.g., "The 2 Bears" vs "YESUNG")
        artist_penalty = (artist_match_threshold - artist_score) * 0.5  # Scale penalty
        text_score = max(0.0, text_score - artist_penalty)
    
    # Penalty for remixes/edits if original doesn't have them
    remix_penalty = 0.0
    amazon_lower = amazon_title.lower()
    spotify_lower = spotify_title.lower()
    has_remix_in_amazon = any(word in amazon_lower for word in ["remix", "edit", "version", "mix"])
    has_remix_in_spotify = any(word in spotify_lower for word in ["remix", "edit", "version", "mix"])
    if has_remix_in_amazon and not has_remix_in_spotify:
        remix_penalty = -0.15  # Penalize remixes when original doesn't have them
    
    # Conditional URL boost - only boost /tracks/ if artist match is good
    # Prefer /tracks/ URLs over /albums/, but not if artist connection is weaker
    url_boost = 0.0
    album_penalty = 0.0
    if amazon_url:
        url_lower = amazon_url.lower()
        if "/tracks/" in url_lower:
            # Only boost if artist match is decent (>= 0.6)
            if artist_score >= 0.6:
                url_boost = 0.1  # +10 points for tracks with good artist match
            else:
                url_boost = 0.05  # Smaller boost if artist match is weaker
        elif "/albums/" in url_lower:
            # Penalize albums, especially if artist match is weak
            if artist_score < 0.6:
                url_boost = -0.15  # -15 points for albums with weak artist match
            else:
                url_boost = -0.05  # -5 points for albums even with good artist match
            
            # Additional album-specific penalty - albums match less precisely than tracks
            # Scale penalty based on how well title matches (if title match is good, less penalty)
            if title_score < 0.7:
                album_penalty = -0.1  # -10 points if title doesn't match well on album
    
    # Final score (0-100)
    final_score = min(100.0, max(0.0, (text_score + remix_penalty + url_boost + album_penalty) * 100.0))
    
    if return_details:
        details = {
            "title_tokens": spotify_title_tokens_list,
            "artist_tokens": spotify_artist_tokens_list,
            "amazon_tokens": amazon_tokens_list,
            "title_token_scores": title_token_scores,
            "artist_token_scores": artist_token_scores,
            "artist_token_matches": artist_token_matches,  # Which Amazon token matched each artist token
            "title_coverage": title_coverage,
            "artist_coverage": artist_coverage,
            "title_avg_token_score": title_avg_token_score,
            "artist_avg_token_score": artist_avg_token_score,
            "title_fuzzy": title_fuzzy,
            "artist_fuzzy": artist_fuzzy,
            "title_score": title_score,
            "artist_score": artist_score,
            "text_score": text_score,
            "artist_penalty": artist_penalty,
            "remix_penalty": remix_penalty,
            "url_boost": url_boost,
            "album_penalty": album_penalty,
            "final_score": final_score,
        }
        return (final_score, details)
    
    return final_score
