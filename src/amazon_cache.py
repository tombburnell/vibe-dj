"""Amazon search result caching.

Caches Amazon Music search results to avoid duplicate searches.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .amazon_music import AmazonSearchResult

logger = logging.getLogger(__name__)


@dataclass
class CachedResult:
    """Cached Amazon search result entry."""

    query: str
    results: list[dict[str, Any]]
    cached_at: str


class AmazonCache:
    """Manages Amazon search result cache."""

    def __init__(self, cache_file: Path = Path(".amazon-cache")) -> None:
        """Initialize cache manager.

        Args:
            cache_file: Path to cache file (default: .amazon-cache)
        """
        self.cache_file = cache_file
        self.cache_data = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        """Load cache from JSON file.

        Returns:
            Cache data dictionary
        """
        if not self.cache_file.exists():
            return {"cache_version": "1.0", "entries": {}}

        try:
            with self.cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure entries exist
                if "entries" not in data:
                    data["entries"] = {}
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache file {self.cache_file}: {e}")
            return {"cache_version": "1.0", "entries": {}}

    def get(self, cache_key: str) -> list[AmazonSearchResult] | None:
        """Get cached results for a key.

        Args:
            cache_key: Cache key (normalized artist|title)

        Returns:
            List of AmazonSearchResult objects, empty list if "no results" was cached,
            or None if not cached
        """
        if cache_key not in self.cache_data["entries"]:
            return None

        try:
            entry = self.cache_data["entries"][cache_key]
            # Check if this is a "no results found" marker (empty results list)
            if not entry.get("results"):
                return []  # Return empty list to indicate "no results" was cached
            
            # Deserialize results
            results = []
            for result_dict in entry["results"]:
                result = AmazonSearchResult(
                    title=result_dict["title"],
                    artist=result_dict["artist"],
                    album=result_dict.get("album"),
                    url=result_dict.get("url"),
                    price=result_dict.get("price"),
                    match_score=result_dict.get("match_score", 0.0),
                    page_title=result_dict.get("page_title"),
                )
                results.append(result)
            return results
        except (KeyError, TypeError) as e:
            logger.warning(f"Failed to deserialize cache entry for {cache_key}: {e}")
            return None

    def set(self, cache_key: str, results: list[AmazonSearchResult]) -> None:
        """Store results in cache.

        Args:
            cache_key: Cache key (normalized artist|title)
            results: List of AmazonSearchResult objects to cache.
                     Empty list is cached to mark "no results found" and avoid
                     repeated searches for tracks that don't exist on Amazon.
        """
        # Serialize results
        results_dict = []
        for result in results:
            result_dict = {
                "title": result.title,
                "artist": result.artist,
                "album": result.album,
                "url": result.url,
                "price": result.price,
                "match_score": result.match_score,
                "page_title": result.page_title,
            }
            results_dict.append(result_dict)

        # Store entry
        self.cache_data["entries"][cache_key] = {
            "query": cache_key,
            "results": results_dict,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        """Persist cache to disk."""
        try:
            # Ensure directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

            with self.cache_file.open("w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.warning(f"Failed to save cache file {self.cache_file}: {e}")


def generate_cache_key(artist: str, title: str, album: str | None = None) -> str:
    """Generate cache key from track metadata.

    Uses normalized artist and title (same normalization as matching).

    Args:
        artist: Artist name
        title: Track title
        album: Album name (optional)

    Returns:
        Cache key string (normalized artist|title or artist|title|album)
    """
    from .track_normalizer import normalize_text

    artist_norm = normalize_text(artist)
    title_norm = normalize_text(title)

    if album:
        album_norm = normalize_text(album)
        return f"{artist_norm}|{title_norm}|{album_norm}"
    else:
        return f"{artist_norm}|{title_norm}"
