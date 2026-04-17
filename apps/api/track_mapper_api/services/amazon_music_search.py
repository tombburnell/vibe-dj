"""Amazon Music search (DuckDuckGo + Amazon HTML fallback) for purchase links."""

from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import requests
from bs4 import BeautifulSoup

from track_mapper_api.config import MAX_WEB_RESULTS
from track_mapper_api.services.link_match_scoring import (
    match_query_for_track,
    score_artist_title_against_query,
)

logger = logging.getLogger(__name__)

# Single DDG request cap (library / provider practical limit).
DDG_TEXT_MAX_RESULTS = 50


@runtime_checkable
class TrackLike(Protocol):
    title: str
    artist: str


@dataclass
class AmazonSearchResult:
    title: str
    artist: str
    album: str | None = None
    url: str | None = None
    price: str | None = None
    match_score: float = 0.0
    page_title: str | None = None


class AmazonMusicSearcher:
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
        self.use_duckduckgo = use_duckduckgo
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.cookies.set("session-id", "", domain=".amazon.com")
        self.session.cookies.set("session-id-time", "", domain=".amazon.com")

    def search_track(
        self,
        track: TrackLike,
        *,
        max_results: int = MAX_WEB_RESULTS,
    ) -> list[AmazonSearchResult]:
        if self.use_duckduckgo:
            return self._search_via_duckduckgo(track, max_results=max_results)
        query = self._build_search_query(track)
        return self._search_amazon(query, max_results=max_results)

    def _build_search_query(self, track: TrackLike) -> str:
        return f'"{track.artist}" "{track.title}"'

    def _duckduckgo_query(self, track: TrackLike) -> str:
        """One site-restricted query (single DDG request)."""
        title = (track.title or "").strip()
        artist = (track.artist or "").strip()
        if artist:
            return f'site:music.amazon.com "{title}" "{artist}"'
        return f'site:music.amazon.com "{title}"'

    def _search_amazon(
        self,
        query: str,
        *,
        max_results: int = MAX_WEB_RESULTS,
    ) -> list[AmazonSearchResult]:
        params = {
            "k": query,
            "i": "digital-music",
            "ref": "sr_nr_n_0",
        }
        try:
            try:
                self.session.get("https://www.amazon.com/", timeout=5)
            except Exception:
                pass
            response = self.session.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Amazon search request failed: %s", e)
            return []
        return self._parse_search_results(response.text, query, max_results=max_results)

    def _parse_search_results(
        self,
        html: str,
        original_query: str,
        *,
        max_results: int = MAX_WEB_RESULTS,
    ) -> list[AmazonSearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[AmazonSearchResult] = []
        product_divs = soup.find_all("div", {"data-asin": True})
        cap = min(max_results, len(product_divs))
        for div in product_divs[:cap]:
            try:
                result = self._parse_product_div(div)
                if result:
                    result.match_score = score_artist_title_against_query(
                        result.artist,
                        result.title,
                        original_query,
                    )
                    results.append(result)
            except Exception:
                continue
        results.sort(key=lambda x: x.match_score, reverse=True)
        return results

    def _parse_product_div(self, div: Any) -> AmazonSearchResult | None:
        try:
            title_elem = div.find("h2") or div.find("span", class_=re.compile("a-text-normal"))
            if not title_elem:
                return None
            title_text = title_elem.get_text(strip=True)
            link_elem = div.find("a", href=re.compile("/dp/|/gp/product/"))
            url = None
            if link_elem and link_elem.get("href"):
                href = link_elem["href"]
                if href.startswith("/"):
                    url = f"https://www.amazon.com{href}"
                else:
                    url = href
            artist_elem = div.find("span", class_=re.compile("a-size-base"))
            artist = "Unknown Artist"
            if artist_elem:
                artist_text = artist_elem.get_text(strip=True)
                if "by" in artist_text.lower():
                    parts = artist_text.split("by", 1)
                    if len(parts) > 1:
                        artist = parts[1].strip()
                else:
                    artist = artist_text
            price_elem = div.find("span", class_=re.compile("a-price"))
            price = None
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r"\$[\d.]+", price_text)
                if price_match:
                    price = price_match.group(0)
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

    def _search_via_duckduckgo(
        self,
        track: TrackLike,
        *,
        max_results: int = MAX_WEB_RESULTS,
    ) -> list[AmazonSearchResult]:
        try:
            from ddgs import DDGS
        except ImportError:
            logger.warning("ddgs not installed; using direct Amazon search")
            return self._search_amazon(
                self._build_search_query(track),
                max_results=max_results,
            )

        query = self._duckduckgo_query(track)
        ddg_ask = min(DDG_TEXT_MAX_RESULTS, max(1, max_results))
        all_results: list[AmazonSearchResult] = []
        try:
            with DDGS() as ddgs:
                try:
                    ddg_results = list(ddgs.text(query, max_results=ddg_ask))
                except Exception:
                    ddg_results = []
                for ddg_result in ddg_results:
                    url = ddg_result.get("href", "")
                    title = ddg_result.get("title", "")
                    body = ddg_result.get("body", "")
                    if "amazon.com" not in url.lower():
                        continue
                    url_lower = url.lower()
                    if "/podcasts/" in url_lower or "/podcast/" in url_lower:
                        continue
                    is_track = "/tracks/" in url_lower
                    is_album = "/albums/" in url_lower
                    if not (is_track or is_album):
                        continue
                    price = None
                    price_match = re.search(r"\$[\d.]+", body)
                    if price_match:
                        price = price_match.group(0)
                    artist = track.artist
                    result_title = track.title
                    if " - " in title:
                        parts = title.split(" - ", 1)
                        if len(parts) == 2:
                            result_title = parts[0].strip()
                            artist = parts[1].strip()
                    elif title:
                        result_title = title.strip()
                    match_query = match_query_for_track(track.artist, track.title)
                    match_score = score_artist_title_against_query(
                        artist,
                        result_title,
                        match_query,
                    )
                    if is_track:
                        match_score += 40.0
                    elif is_album:
                        match_score += 20.0
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
                            page_title=page_title,
                        )
                    )
                all_results.sort(key=lambda x: x.match_score, reverse=True)
                top_results = all_results[:max_results]
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
            logger.warning("DuckDuckGo search failed: %s", e)
            return self._search_amazon(
                self._build_search_query(track),
                max_results=max_results,
            )

    def generate_amazon_link(self, track: TrackLike) -> str:
        query = f"{track.artist} {track.title}"
        encoded_query = urllib.parse.quote(query)
        return f"{self.BASE_URL}?k={encoded_query}&i=digital-music"

    def fetch_link_page_title(self, url: str) -> str | None:
        """Load the Amazon product/track page and read og:title or <title> (not DDG snippet)."""
        if not url or "amazon.com" not in url.lower():
            return None
        try:
            response = self.session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.debug("fetch_link_page_title failed for %s: %s", url, e)
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            t = str(og["content"]).strip()
            if len(t) > 2 and t.lower() != "amazon music":
                return re.sub(r"\s+", " ", t)
        tw = soup.find("meta", attrs={"name": "twitter:title"})
        if tw and tw.get("content"):
            t = str(tw["content"]).strip()
            if len(t) > 2 and t.lower() != "amazon music":
                return re.sub(r"\s+", " ", t)
        t_el = soup.find("title")
        if t_el:
            t = t_el.get_text(strip=True)
            t = re.sub(r"\s+", " ", t)
            if len(t) > 2 and t.lower() != "amazon music":
                return t
        return None
