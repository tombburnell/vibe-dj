"""Multi-site web search (``ddgs`` or Serper) for purchase/stream links (configurable sites + URL filters)."""

from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Literal

import requests

import track_mapper_api.config as api_config
from track_mapper_api.config import MAX_WEB_RESULTS
from track_mapper_api.services.link_match_scoring import (
    match_query_for_track,
    score_web_hit_snippet,
)

logger = logging.getLogger(__name__)

# After per-domain score ranking, keep at most this many hits per ``matched_domain``.
MAX_HITS_PER_DOMAIN = 2

DDG_TEXT_MAX_RESULTS = 50
# ddgs.text ``backend``: one name or comma-separated list. Use ``auto`` / ``all`` for full metasearch.
# mojeek 403
# Text engines (ddgs): brave, duckduckgo, google, grokipedia, mojeek, wikipedia, yahoo, yandex
# DDGS_TEXT_BACKEND = "brave"
DDGS_TEXT_BACKEND = "brave"

SERPER_SEARCH_URL = "https://google.serper.dev/search"

WebSearchProvider = Literal["serper", "ddg"]


def _repeat_url_for_ddg_backend(query_quoted: str) -> str:
    primary = DDGS_TEXT_BACKEND.split(",")[0].strip().lower()
    if primary == "brave":
        return f"https://search.brave.com/search?q={query_quoted}&source=web"
    if primary == "google":
        return f"https://www.google.com/search?q={query_quoted}&hl=en"
    return f"https://duckduckgo.com/?q={query_quoted}"


def multisite_repeat_search_url(
    query: str,
    *,
    web_search_provider: WebSearchProvider | None = None,
) -> str:
    """Open the same multisite query in a browser.

    ``web_search_provider`` forces Serper→Google vs ``ddgs`` (Brave by default); when omitted, uses
    env (``USE_SERPER`` / ``SERPER_API_KEY``).
    """
    q = urllib.parse.quote(query, safe="")
    if web_search_provider == "serper":
        return f"https://www.google.com/search?q={q}&hl=en"
    if web_search_provider == "ddg":
        return _repeat_url_for_ddg_backend(q)
    if api_config.USE_SERPER and api_config.SERPER_API_KEY:
        return f"https://www.google.com/search?q={q}&hl=en"
    return _repeat_url_for_ddg_backend(q)


try:
    from ddgs import DDGS
except ImportError:
    DDGS = None  # type: ignore[misc, assignment]


def ddg_search(*, query: str, max_results: int, backend: str | None = None) -> list[dict[str, Any]]:
    """Run ``ddgs`` text search; returns rows with ``href``, ``title``, ``body`` (same shape as upstream)."""
    if DDGS is None:
        logger.warning("ddgs not installed; multi-site web search unavailable")
        return []
    be = backend if backend is not None else DDGS_TEXT_BACKEND
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, backend=be))
    except Exception as ex:
        logger.warning("ddgs text search failed: %s", ex)
        return []


def serper_search(*, query: str, max_results: int, api_key: str) -> list[dict[str, str]]:
    """POST to Serper Google search; normalize organic hits to ``href`` / ``title`` / ``body``.

    Payload matches Serper docs (``q`` only). Result list is capped to ``max_results`` client-side.
    """
    key = (api_key or "").strip()
    if not key:
        return []
    cap = max(0, max_results)
    try:
        resp = requests.post(
            SERPER_SEARCH_URL,
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as ex:
        detail = ""
        if ex.response is not None and ex.response.text:
            detail = ex.response.text[:500]
        logger.warning("serper search failed: %s response_body=%r", ex, detail)
        return []
    except (requests.RequestException, ValueError, TypeError) as ex:
        logger.warning("serper search failed: %s", ex)
        return []
    organic = data.get("organic")
    if not isinstance(organic, list):
        return []
    out: list[dict[str, str]] = []
    for item in organic:
        if not isinstance(item, dict):
            continue
        link = (item.get("link") or "").strip()
        if not link:
            continue
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        out.append({"href": link, "title": title, "body": snippet})
        if len(out) >= cap:
            break
    return out


@dataclass(frozen=True)
class SiteSearchRule:
    """One searchable domain, optional URL rewrites, and path-only exclusion regexes."""

    domain: str
    #: Matched only against the URL **path** (not query), after transforms.
    url_exclude_patterns: tuple[str, ...] = ()
    #: ``(regex, repl)`` pairs applied in order via ``re.sub`` (on the original URL first).
    url_transforms: tuple[tuple[str, str], ...] = ()
    #: ``(regex, repl)`` pairs applied to SERP ``title`` after URL filters (repl often ``""``).
    title_transforms: tuple[tuple[str, str], ...] = ()

    def compiled_excludes(self) -> tuple[re.Pattern[str], ...]:
        return tuple(re.compile(p, re.IGNORECASE) for p in self.url_exclude_patterns)

    def compiled_transforms(self) -> tuple[tuple[re.Pattern[str], str], ...]:
        return tuple((re.compile(p, re.IGNORECASE), repl) for p, repl in self.url_transforms)

    def compiled_title_transforms(self) -> tuple[tuple[re.Pattern[str], str], ...]:
        return tuple((re.compile(p, re.IGNORECASE), repl) for p, repl in self.title_transforms)


@dataclass
class WebSearchHit:
    url: str
    title: str
    body: str
    matched_domain: str | None = None
    #: Fuzzy relevance 0–100; set in :meth:`MultiSiteWebSearcher.search` after filters/dedupe.
    match_score: float = 0.0


def _host_matches_domain(host: str, domain: str) -> bool:
    host = host.lower().split(":")[0].strip(".")
    d = domain.lower().strip(".")
    return host == d or host.endswith("." + d)


def _site_for_url(url: str, rules: tuple[SiteSearchRule, ...]) -> SiteSearchRule | None:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc or ""
    except Exception:
        return None
    if not host:
        return None
    for rule in rules:
        if _host_matches_domain(host, rule.domain):
            return rule
    return None


# Regional storefronts use the same Amazon SERP title noise as amazon.com; ``_site_for_url`` only
# knows ``domain="amazon.com"`` (covers *.amazon.com), so :func:`display_link_title` extends matching.
_AMAZON_STOREFRONT_SUFFIXES: tuple[str, ...] = (
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.nl",
    "amazon.se",
    "amazon.pl",
    "amazon.in",
    "amazon.ca",
    "amazon.cn",
    "amazon.ae",
    "amazon.sa",
    "amazon.eg",
    "amazon.co.jp",
    "amazon.jp",
    "amazon.com.au",
    "amazon.com.mx",
    "amazon.com.br",
    "amazon.com.be",
    "amazon.com.tr",
)


def _host_is_amazon_storefront(host: str) -> bool:
    h = host.lower().split(":")[0].strip(".")
    if not h:
        return False
    if _host_matches_domain(h, "amazon.com"):
        return True
    return any(h == suffix or h.endswith("." + suffix) for suffix in _AMAZON_STOREFRONT_SUFFIXES)


def _amazon_title_rule(rules: tuple[SiteSearchRule, ...]) -> SiteSearchRule | None:
    for r in rules:
        if r.domain == "amazon.com":
            return r
    return None


def _url_path_for_matching(url: str) -> str:
    """Path-only haystack for excludes; avoids false positives from query strings (e.g. ?next=/browse/artist/)."""
    try:
        p = urllib.parse.urlsplit(url.strip())
        return p.path or "/"
    except Exception:
        return url


def _first_exclude_pattern_match(url: str, compiled: tuple[re.Pattern[str], ...]) -> str | None:
    haystack = _url_path_for_matching(url)
    for pat in compiled:
        if pat.search(haystack):
            return pat.pattern
    return None


def _url_excluded_by_url_patterns(url: str, compiled: tuple[re.Pattern[str], ...]) -> bool:
    return _first_exclude_pattern_match(url, compiled) is not None


def _apply_url_transforms(
    url: str,
    pairs: tuple[tuple[re.Pattern[str], str], ...],
) -> str:
    out = url
    for pat, repl in pairs:
        out = pat.sub(repl, out)
    return out


def _apply_title_transforms(
    title: str,
    pairs: tuple[tuple[re.Pattern[str], str], ...],
) -> str:
    out = title
    for pat, repl in pairs:
        out = pat.sub(repl, out)
    return out.strip()


def _normalize_netloc_for_dedupe(netloc: str) -> str:
    """Merge tidal subdomains so listen.tidal.com/album/1 and tidal.com/album/1 dedupe."""
    h = netloc.lower().split(":")[0]
    if h == "tidal.com" or h.endswith(".tidal.com"):
        return "tidal.com"
    return h


def _canonical_url_key(url: str) -> str:
    """Dedupe key: scheme + normalized host + path, lowercased; query/fragment ignored."""
    try:
        p = urllib.parse.urlsplit(url.strip())
    except Exception:
        return url.strip().lower()
    scheme = (p.scheme or "https").lower()
    netloc = _normalize_netloc_for_dedupe(p.netloc)
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return f"{scheme}://{netloc}{path}".lower()


def default_site_rules() -> tuple[SiteSearchRule, ...]:
    """Default ordered sites; per-domain URL excludes drop non-track-style pages."""
    return (
        SiteSearchRule(
            domain="tidal.com",
            url_exclude_patterns=(r"/browse/artist/",),
            url_transforms=(
                # /browse/album/{id} redirects to /album/{id}
                (r"/browse/album/", "/album/"),
            ),
            title_transforms=((r"\s+on\s+TIDAL\s*$", ""),),
        ),
        SiteSearchRule(
            domain="amazon.com",
            url_exclude_patterns=(
                r"/albums?/",
                r"/album(/|$|\?)",
                r"/artists?/",
            ),
            title_transforms=(
                # e.g. "Amazon.com: Blondie Mix."
                (r"^Amazon\.com:\s*", ""),
                # Long SERP clause first (before stripping a shorter leading "Play ")
                (r"\s+Play\s+from\s+beginning.*$", ""),
                # "Play Track by Artist on Amazon Music Unlimited [— …]"
                (r"\s+on\s+Amazon\s+Music\s+Unlimited(?:\s*[—–]\s*.+)?\s*$", ""),
                (r"^Play\s+", ""),
                # "… [Explicit] song by X from Album … — Artist"
                (r"\s+song\s+by\s+.+?\s+from\s+.+$", ""),
                # "… - music.amazon.com"
                (r"\s+[-–—\u2212]\s*music\.amazon\.com\s*$", ""),
                (r"\s+--+\s*music\.amazon\.com\s*$", ""),
                # "… - Amazon.com Music", "… — amazon.com" (ASCII/en/em/minus, or repeated hyphens)
                (r"\s+[-–—\u2212]\s*Amazon(?:\.com)?(?:\s+Music)?\s*$", ""),
                (r"\s+--+\s*Amazon(?:\.com)?(?:\s+Music)?\s*$", ""),
                # After domain tail: SERP "… on Amazon Music — amazon.com" → drop trailing clause
                (r"\s+on\s+Amazon\s+Music\s*$", ""),
                # e.g. "… : Armand Van Helden: Digital Music"
                (r"\s*:\s*Digital\s+Music\s*$", ""),
            ),
        ),
        SiteSearchRule(
            domain="soundcloud.com",
            url_exclude_patterns=(
                r"/sets/",
                # Profile / artist root only: /handle or /handle/ — need at least /handle/slug
                r"^/[^/]+/?$",
            ),
            title_transforms=(
                # e.g. "Stream Track …" (SERP boilerplate)
                (r"^Stream\s+", ""),
                # e.g. "… | Listen online for free — soundcloud.com"
                (r"\s*\|\s*Listen online for free.*$", ""),
                # e.g. "… | Listen to songs, albums, playlists for free — soundcloud.com"
                (r"\s*\|\s*Listen to songs.*$", ""),
                (r"\s+on\s+SoundCloud.*$", ""),
                # "… -/--/—/–/− SoundCloud" at end (brand suffix without domain)
                (r"\s+[-–—\u2212]\s*SoundCloud\s*$", ""),
                (r"\s+--+\s*SoundCloud\s*$", ""),
                # "… -/--/—/–/− soundcloud.com" (ASCII hyphen and common unicode dashes)
                (r"\s+[-–—\u2212]\s*soundcloud\.com.*$", ""),
                (r"\s+--+\s*soundcloud\.com.*$", ""),
            ),
        ),
    )


def display_link_title(url: str | None, title: str | None) -> str | None:
    """Apply :func:`default_site_rules` title regexes using ``url``'s host.

    Use when serializing stored ``amazon_link_title`` / candidate titles so older DB rows match
    on-ingest cleanup (transforms are idempotent for already-clean strings).
    """
    if title is None:
        return None
    t = str(title).strip()
    if not t:
        return None
    if not url or not str(url).strip():
        return t
    u = str(url).strip()
    rules = default_site_rules()
    rule = _site_for_url(u, rules)
    if rule is None:
        try:
            host = urllib.parse.urlparse(u).netloc or ""
        except Exception:
            host = ""
        if host and _host_is_amazon_storefront(host):
            rule = _amazon_title_rule(rules)
    if rule is None:
        return t
    pairs = rule.compiled_title_transforms()
    if not pairs:
        return t
    out = _apply_title_transforms(t, pairs).strip()
    return out if out else None


def build_multisite_ddg_query(
    *,
    artist: str,
    track: str,
    sites: tuple[SiteSearchRule, ...],
    suffix: str = "",
) -> str:
    """Single DDG query: (site:x OR site:y) artist track suffix."""
    site_parts = [f"site:{s.domain}" for s in sites]
    site_clause = "(" + " OR ".join(site_parts) + ")"
    a = (artist or "").strip()
    t = (track or "").strip()
    return f"{site_clause} {a} {t} {suffix}".strip()


class MultiSiteWebSearcher:
    """Text search via Serper or ``ddgs`` (see ``USE_SERPER`` / ``SERPER_API_KEY``); filter hits per-site by URL regexes."""

    def __init__(
        self,
        *,
        sites: tuple[SiteSearchRule, ...] | None = None,
        query_suffix: str = "",
    ) -> None:
        self.sites: tuple[SiteSearchRule, ...] = sites if sites is not None else default_site_rules()
        self.query_suffix = query_suffix
        self._compiled: dict[str, tuple[re.Pattern[str], ...]] = {
            r.domain: r.compiled_excludes() for r in self.sites
        }
        self._transforms: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
            r.domain: r.compiled_transforms() for r in self.sites
        }
        self._title_transforms: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
            r.domain: r.compiled_title_transforms() for r in self.sites
        }

    def build_query(self, *, artist: str, track: str) -> str:
        return build_multisite_ddg_query(
            artist=artist,
            track=track,
            sites=self.sites,
            suffix=self.query_suffix,
        )

    def search(
        self,
        *,
        artist: str,
        track: str,
        max_results: int = MAX_WEB_RESULTS,
        trace: bool = False,
        web_search_provider: WebSearchProvider | None = None,
    ) -> tuple[str, list[WebSearchHit]]:
        """Returns (query_string, hits_after_filters and scoring).

        After URL filters and dedupe, titles are cleaned per :class:`SiteSearchRule.title_transforms`,
        then each hit is scored with :mod:`link_match_scoring`. Within each domain, only the top
        :data:`MAX_HITS_PER_DOMAIN` by score are kept; results are then sorted globally by score
        (ties: site order, then backend row order) and truncated to ``max_results``.

        ``web_search_provider``: ``"serper"`` / ``"ddg"`` overrides env for this call only.

        Set ``trace=True`` to log human-readable FILTERED / TRANSFORMED / DEDUPED lines (INFO).
        """
        query = self.build_query(artist=artist, track=track)
        # Fetch enough raw rows to reorder by domain; then slice to max_results.
        fetch_n = min(DDG_TEXT_MAX_RESULTS, max(25, max_results))
        site_index_by_domain = {r.domain: i for i, r in enumerate(self.sites)}
        staged: list[tuple[int, int, WebSearchHit]] = []

        if web_search_provider == "serper":
            provider = "serper"
            key = api_config.SERPER_API_KEY.strip()
            if not key:
                logger.warning("web search serper requested but SERPER_API_KEY is empty")
                raw = []
            else:
                raw = serper_search(query=query, max_results=fetch_n, api_key=key)
        elif web_search_provider == "ddg":
            provider = "ddg"
            raw = ddg_search(query=query, max_results=fetch_n)
        elif api_config.USE_SERPER and api_config.SERPER_API_KEY:
            provider = "serper"
            raw = serper_search(
                query=query, max_results=fetch_n, api_key=api_config.SERPER_API_KEY
            )
        else:
            provider = "ddg"
            raw = ddg_search(query=query, max_results=fetch_n)

        try:
            if trace:
                logger.info("")
                logger.info("Raw search rows: %s", len(raw))
            for row_index, row in enumerate(raw):
                url = (row.get("href") or "").strip()
                title = (row.get("title") or "").strip()
                body = (row.get("body") or "").strip()
                if not url:
                    if trace:
                        logger.info(
                            "SKIPPED: (empty URL) row=%s title=%r",
                            row_index,
                            (title[:72] + "...") if len(title) > 72 else title,
                        )
                    continue
                rule = _site_for_url(url, self.sites)
                if rule is None:
                    if trace:
                        logger.info("SKIPPED: (no configured site) %s", url)
                    continue
                transforms = self._transforms.get(rule.domain, ())
                url_final = (
                    _apply_url_transforms(url, transforms).strip() if transforms else url
                )
                if url_final != url and trace:
                    logger.info("TRANSFORMED: %s => %s", url, url_final)
                if not url_final:
                    if trace:
                        logger.info("SKIPPED: (empty after transform) %s", url)
                    continue
                compiled = self._compiled.get(rule.domain, ())
                matched_pat = (
                    _first_exclude_pattern_match(url_final, compiled) if compiled else None
                )
                if matched_pat is not None:
                    if trace:
                        logger.info(
                            "FILTERED: %s  (%s)",
                            url_final,
                            matched_pat,
                        )
                    continue
                title_pairs = self._title_transforms.get(rule.domain, ())
                title_clean = (
                    _apply_title_transforms(title, title_pairs) if title_pairs else title
                )
                if title_clean != title and trace:
                    logger.info("TITLE: %r => %r", title, title_clean)
                site_i = site_index_by_domain[rule.domain]
                staged.append(
                    (
                        site_i,
                        row_index,
                        WebSearchHit(
                            url=url_final,
                            title=title_clean,
                            body=body,
                            matched_domain=rule.domain,
                        ),
                    )
                )
        except Exception as ex:
            logger.warning("Multi-site web search error: %s", ex)
            logger.info(
                "multisite web search provider=%s raw_rows=%d returned_hits=%d",
                provider,
                len(raw),
                0,
            )
            return query, []

        staged.sort(key=lambda t: (t[0], t[1]))
        seen_keys: set[str] = set()
        deduped: list[tuple[int, int, WebSearchHit]] = []
        for _si, _di, hit in staged:
            key = _canonical_url_key(hit.url)
            if key in seen_keys:
                if trace:
                    logger.info("DEDUPED: %s", hit.url)
                continue
            seen_keys.add(key)
            deduped.append((_si, _di, hit))

        match_q = match_query_for_track(artist, track)
        by_domain: dict[str, list[tuple[float, int, int, WebSearchHit]]] = {}
        for site_i, ddg_i, hit in deduped:
            hit.match_score = score_web_hit_snippet(hit, match_q)
            dom = hit.matched_domain or ""
            by_domain.setdefault(dom, []).append((hit.match_score, site_i, ddg_i, hit))
        capped: list[tuple[float, int, int, WebSearchHit]] = []
        for _dom, items in by_domain.items():
            items.sort(key=lambda t: (-t[0], t[1], t[2]))
            capped.extend(items[:MAX_HITS_PER_DOMAIN])
        capped.sort(key=lambda t: (-t[0], t[1], t[2]))
        hits = [t[3] for t in capped[:max_results]]
        if trace:
            for h in hits:
                logger.info(
                    "SCORED: %.1f %s (%s)",
                    h.match_score,
                    h.url,
                    h.matched_domain,
                )
        logger.info(
            "multisite web search provider=%s raw_rows=%d returned_hits=%d",
            provider,
            len(raw),
            len(hits),
        )
        return query, hits
