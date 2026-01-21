"""Amazon Music search functionality.

Searches Amazon Music for tracks and generates purchase/download links.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    from spotify_client import Track
except ImportError:
    try:
        from track_db import Track
    except ImportError:
        from .spotify_client import Track


@dataclass
class AmazonSearchResult:
    """Represents an Amazon Music search result."""

    title: str
    artist: str
    album: str | None = None
    url: str | None = None
    price: str | None = None
    match_score: float = 0.0
    page_title: str | None = None  # HTML title of the Amazon page


class AmazonMusicSearcher:
    """Search Amazon Music for tracks."""

    BASE_URL = "https://www.amazon.com/s"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.amazon.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "max-age=0",
    }

    def __init__(self, use_duckduckgo: bool = True) -> None:
        """Initialize the searcher.
        
        Args:
            use_duckduckgo: If True, use DuckDuckGo search instead of direct Amazon scraping
        """
        self.use_duckduckgo = use_duckduckgo
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        # Set cookies to appear more like a real browser
        self.session.cookies.set("session-id", "", domain=".amazon.com")
        self.session.cookies.set("session-id-time", "", domain=".amazon.com")

    def search_track(self, track: Track) -> list[AmazonSearchResult]:
        """Search Amazon Music for a track.

        Args:
            track: Track to search for

        Returns:
            List of search results
        """
        if self.use_duckduckgo:
            return self._search_via_duckduckgo(track)
        else:
            query = self._build_search_query(track)
            return self._search_amazon(query)

    def _build_search_query(self, track: Track) -> str:
        """Build search query from track metadata.

        Args:
            track: Track object

        Returns:
            Search query string
        """
        # Format: "artist title" or "artist - title"
        query = f'"{track.artist}" "{track.title}"'
        return query

    def _search_amazon(self, query: str) -> list[AmazonSearchResult]:
        """Search Amazon Music.

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        params = {
            "k": query,
            "i": "digital-music",  # Digital music category
            "ref": "sr_nr_n_0",
        }

        try:
            # First, try to get the main Amazon page to establish session
            # This helps avoid 503 errors by looking like a real browser flow
            try:
                self.session.get("https://www.amazon.com/", timeout=5)
            except Exception:
                pass  # Ignore errors on this initial request
            
            response = self.session.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Warning: Failed to search Amazon: {e}")
            return []

        return self._parse_search_results(response.text, query)

    def _parse_search_results(
        self, html: str, original_query: str
    ) -> list[AmazonSearchResult]:
        """Parse Amazon search results HTML.

        Args:
            html: HTML content from Amazon search
            original_query: Original search query

        Returns:
            List of search results
        """
        soup = BeautifulSoup(html, "html.parser")
        results: list[AmazonSearchResult] = []

        # Find product containers (Amazon's structure may vary)
        # Look for divs with data-asin attribute (product ASINs)
        product_divs = soup.find_all("div", {"data-asin": True})

        for div in product_divs[:10]:  # Limit to top 10 results
            try:
                result = self._parse_product_div(div)
                if result:
                    # Calculate match score
                    result.match_score = self._calculate_match_score(
                        result, original_query
                    )
                    results.append(result)
            except Exception as e:
                # Skip products that fail to parse
                continue

        # Sort by match score
        results.sort(key=lambda x: x.match_score, reverse=True)
        return results

    def _parse_product_div(self, div: Any) -> AmazonSearchResult | None:
        """Parse a product div into AmazonSearchResult.

        Args:
            div: BeautifulSoup element

        Returns:
            AmazonSearchResult or None
        """
        try:
            # Find title/link
            title_elem = div.find("h2") or div.find("span", class_=re.compile("a-text-normal"))
            if not title_elem:
                return None

            title_text = title_elem.get_text(strip=True)

            # Find link
            link_elem = div.find("a", href=re.compile("/dp/|/gp/product/"))
            url = None
            if link_elem and link_elem.get("href"):
                href = link_elem["href"]
                if href.startswith("/"):
                    url = f"https://www.amazon.com{href}"
                else:
                    url = href

            # Find artist (usually in a span with specific class)
            artist_elem = div.find("span", class_=re.compile("a-size-base"))
            artist = "Unknown Artist"
            if artist_elem:
                artist_text = artist_elem.get_text(strip=True)
                # Try to extract artist from text
                if "by" in artist_text.lower():
                    parts = artist_text.split("by", 1)
                    if len(parts) > 1:
                        artist = parts[1].strip()
                else:
                    artist = artist_text

            # Find price
            price_elem = div.find("span", class_=re.compile("a-price"))
            price = None
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r"\$[\d.]+", price_text)
                if price_match:
                    price = price_match.group(0)

            # Extract title and artist from title_text if needed
            if " - " in title_text:
                parts = title_text.split(" - ", 1)
                artist = parts[0].strip()
                title_text = parts[1].strip()

            return AmazonSearchResult(
                title=title_text,
                artist=artist,
                url=url,
                price=price,
            )
        except Exception:
            return None

    def _calculate_match_score(self, result: AmazonSearchResult, query: str) -> float:
        """Calculate how well a result matches the query.

        Args:
            result: Search result
            query: Original search query

        Returns:
            Match score (0-100)
        """
        from rapidfuzz import fuzz

        # Normalize for comparison
        result_str = f"{result.artist} {result.title}".lower()
        query_lower = query.lower()

        # Use token sort ratio for fuzzy matching
        score = fuzz.token_sort_ratio(result_str, query_lower)
        return score

    def _search_via_duckduckgo(self, track: Track) -> list[AmazonSearchResult]:
        """Search Amazon Music via DuckDuckGo to bypass bot detection.

        Prioritizes track/album URLs over artist pages.

        Args:
            track: Track to search for

        Returns:
            List of search results (filtered to prefer tracks/albums over artist pages)
        """
        try:
            from ddgs import DDGS
        except ImportError:
            # Fallback to old package name for compatibility
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                print("Warning: ddgs not installed. Falling back to direct Amazon search.")
                query = self._build_search_query(track)
                return self._search_amazon(query)

        # Build queries prioritizing track name over artist
        # Try track-specific queries first (prioritize track name)
        queries = [
            # Track name first, then artist (most specific)
            f'site:music.amazon.com "{track.title}" "{track.artist}"',
            # Track name only (broader search)
            f'site:music.amazon.com "{track.title}"',
            # Both together (original order)
            f'site:music.amazon.com "{track.artist}" "{track.title}"',
            # General Amazon search with track prioritized
            f'site:amazon.com "{track.title}" "{track.artist}" digital music',
        ]
        
        all_results: list[AmazonSearchResult] = []
        seen_urls: set[str] = set()
        
        try:
            with DDGS() as ddgs:
                for query in queries:
                    try:
                        ddg_results = list(ddgs.text(query, max_results=5))
                        
                        for ddg_result in ddg_results:
                            url = ddg_result.get("href", "")
                            title = ddg_result.get("title", "")
                            body = ddg_result.get("body", "")
                            
                            # Filter to only Amazon URLs
                            if "amazon.com" not in url.lower():
                                continue
                            
                            url_lower = url.lower()
                            
                            # Skip podcasts - only want tracks/albums
                            if "/podcasts/" in url_lower or "/podcast/" in url_lower:
                                continue
                            
                            # Only accept /tracks/ or /albums/ URLs
                            is_track = "/tracks/" in url_lower
                            is_album = "/albums/" in url_lower
                            
                            if not (is_track or is_album):
                                continue  # Skip non-track/album URLs
                            
                            # Skip if we've already seen this URL
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)
                            
                            # Skip artist pages - prefer tracks/albums
                            # Artist pages typically have /artists/ in the URL
                            is_artist_page = "/artists/" in url_lower
                            
                            # Extract price if mentioned in body
                            price = None
                            price_match = re.search(r"\$[\d.]+", body)
                            if price_match:
                                price = price_match.group(0)
                            
                            # Try to extract artist/title from DuckDuckGo title or body
                            artist = track.artist  # Default to original
                            result_title = track.title  # Default to original
                            
                            # DuckDuckGo title often has format "Title - Artist" or just "Title"
                            if " - " in title:
                                parts = title.split(" - ", 1)
                                if len(parts) == 2:
                                    result_title = parts[0].strip()
                                    artist = parts[1].strip()
                            elif title:
                                # If title exists but no " - ", use it as the track title
                                result_title = title.strip()
                            
                            # Calculate match score
                            match_query = f'"{track.artist}" "{track.title}"'
                            match_score = self._calculate_match_score(
                                AmazonSearchResult(title=result_title, artist=artist),
                                match_query
                            )
                            
                            # Boost score for non-artist pages (tracks/albums)
                            if not is_artist_page:
                                match_score += 20  # Prefer tracks/albums
                            
                            # Use DuckDuckGo title as page_title if available, otherwise construct from parsed data
                            page_title = title if title else None
                            if not page_title and result_title and artist:
                                page_title = f"{result_title} - {artist}"
                            elif not page_title and result_title:
                                page_title = result_title
                            
                            all_results.append(
                                AmazonSearchResult(
                                    title=result_title,
                                    artist=artist,
                                    url=url,
                                    price=price,
                                    match_score=match_score,
                                    page_title=page_title,  # Use DuckDuckGo title directly
                                )
                            )
                    except Exception:
                        continue  # Try next query if this one fails
                
                # Sort by match score (highest first)
                all_results.sort(key=lambda x: x.match_score, reverse=True)
                top_results = all_results[:5]  # Return top 5 results
                
                # Construct page titles from search result data (Amazon HTML doesn't have titles)
                # Format: "Title - Artist" or just "Title" or "Artist"
                for result in top_results:
                    if not result.page_title:
                        if result.title and result.artist:
                            result.page_title = f"{result.title} - {result.artist}"
                        elif result.title:
                            result.page_title = result.title
                        elif result.artist:
                            result.page_title = result.artist
                
                return top_results
                
        except Exception as e:
            print(f"Warning: DuckDuckGo search failed: {e}")
            # Fallback to direct Amazon search
            query = self._build_search_query(track)
            return self._search_amazon(query)
        
        return []
    
    def _fetch_page_title(self, url: str) -> str | None:
        """Fetch HTML title from Amazon page.
        
        Args:
            url: Amazon URL to fetch title from
            
        Returns:
            Page title or None if fetch fails
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                # Clean up Amazon title (remove "Amazon Music:" prefix if present)
                title_text = re.sub(r"^Amazon Music:\s*", "", title_text, flags=re.IGNORECASE)
                return title_text
        except Exception as e:
            logger.debug(f"Failed to fetch page title for {url}: {e}")
            return None

    def generate_amazon_link(self, track: Track) -> str:
        """Generate Amazon Music search URL for a track.

        Args:
            track: Track object

        Returns:
            Amazon search URL
        """
        query = f"{track.artist} {track.title}"
        encoded_query = urllib.parse.quote(query)
        url = f"{self.BASE_URL}?k={encoded_query}&i=digital-music"
        return url


def generate_amazon_report(
    missing_tracks: list[Track], output_path: str | None = None
) -> str:
    """Generate a report with Amazon Music links for missing tracks.

    Args:
        missing_tracks: List of missing tracks
        output_path: Optional path to save report file

    Returns:
        Report text
    """
    searcher = AmazonMusicSearcher()
    report_lines = [
        "Amazon Music Purchase Links Report",
        "=" * 60,
        f"Total tracks: {len(missing_tracks)}",
        "",
    ]

    for i, track in enumerate(missing_tracks, 1):
        report_lines.append(f"{i}. {track.artist} - {track.title}")
        if track.album:
            report_lines.append(f"   Album: {track.album}")

        # Generate Amazon search link
        amazon_url = searcher.generate_amazon_link(track)
        report_lines.append(f"   Amazon: {amazon_url}")

        # Try to find specific results
        try:
            results = searcher.search_track(track)
            if results and results[0].url:
                report_lines.append(f"   Direct: {results[0].url}")
                if results[0].price:
                    report_lines.append(f"   Price: {results[0].price}")
        except Exception:
            pass

        report_lines.append("")

    report_text = "\n".join(report_lines)

    if output_path:
        from pathlib import Path

        Path(output_path).write_text(report_text, encoding="utf-8")
        print(f"Report saved to {output_path}")

    return report_text


def main() -> None:
    """Example usage."""
    try:
        from spotify_client import Track
    except ImportError:
        from .spotify_client import Track

    searcher = AmazonMusicSearcher()

    # Test with a sample track
    test_track = Track(
        title="Kids Go Down",
        artist="Chinese American Bear",
        album=None,
    )

    print(f"Searching Amazon Music for: {test_track.artist} - {test_track.title}")
    results = searcher.search_track(test_track)

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. {result.artist} - {result.title}")
        if result.url:
            print(f"   URL: {result.url}")
        if result.price:
            print(f"   Price: {result.price}")
        print(f"   Match Score: {result.match_score:.1f}%")
        print()


if __name__ == "__main__":
    main()

