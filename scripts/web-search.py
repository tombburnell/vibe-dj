#!/usr/bin/env python3
"""Debug music link search: AmazonMusicSearcher or multi-site web search (ddgs / Serper).

Usage (from repo root):
    uv run python scripts/web-search.py "Shaking Things Up" --artist nimino
    uv run python scripts/web-search.py Shaking Things Up nimino

Multi-site web search (tidal / amazon / soundcloud + per-site URL filters):
    uv run python scripts/web-search.py --web-service Shaking Things Up nimino
    uv run python scripts/web-search.py --web-service "Shaking Things Up" --artist nimino
    uv run python scripts/web-search.py --web-service --serper Shaking Things Up nimino  # Serper API
    uv run python scripts/web-search.py --web-service --ddgs Shaking Things Up nimino   # ddgs (Brave default)

Options:
    --web-service   Use MultiSiteWebSearcher (see track_mapper_api.services.web_search_service).
    --serper        With --web-service: Serper (needs SERPER_API_KEY; overrides USE_SERPER env).
    --ddgs          With --web-service: ddgs only (overrides USE_SERPER env).
    --verbose       With --web-service: FILTERED / TRANSFORMED / DEDUPED lines (stderr).
    --no-ddg        Amazon path only: direct Amazon HTML search (ignored with --web-service).
    --max N         Max results (default: MAX_WEB_RESULTS from config).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

import track_mapper_api.config as api_config  # noqa: E402
from track_mapper_api.config import MAX_WEB_RESULTS  # noqa: E402
from track_mapper_api.services.amazon_music_search import AmazonMusicSearcher  # noqa: E402
from track_mapper_api.services.web_search_service import (  # noqa: E402
    DDGS_TEXT_BACKEND,
    MultiSiteWebSearcher,
    WebSearchProvider,
    multisite_repeat_search_url,
)


def _parse_track_args(title_parts: list[str], artist: str | None) -> SimpleNamespace:
    if artist is not None:
        title = " ".join(title_parts).strip()
        return SimpleNamespace(title=title or "(empty)", artist=artist.strip() or "(empty)")
    if len(title_parts) < 2:
        return SimpleNamespace(title=" ".join(title_parts).strip(), artist="")
    *rest, last = title_parts
    return SimpleNamespace(title=" ".join(rest).strip(), artist=last.strip())


def _run_amazon_mode(track: SimpleNamespace, *, use_ddg: bool, max_results: int) -> int:
    searcher = AmazonMusicSearcher(use_duckduckgo=use_ddg)
    results = searcher.search_track(track, max_results=max_results)

    mode = "DuckDuckGo + Amazon Music URLs" if use_ddg else "Amazon HTML search"
    print(f"Mode: {mode}")
    print(f"Title:  {track.title!r}")
    print(f"Artist: {track.artist!r}")
    print(f"Amazon search URL (fallback): {searcher.generate_amazon_link(track)}")
    print(f"max_results: {max_results}")
    print()

    if not results:
        print("No results.")
        return 1

    with_url = [r for r in results if r.url]
    picked_url = with_url[0].url if with_url else None

    for i, r in enumerate(results, start=1):
        mark = ""
        if r.url and r.url == picked_url:
            mark = "  <<< PICKED (first ranked with URL)"
        print(f"--- #{i}{mark}")
        print(f"  match_score: {r.match_score}")
        print(f"  url:         {r.url}")
        print(f"  title:       {r.title!r}")
        print(f"  artist:      {r.artist!r}")
        if r.page_title:
            print(f"  page_title:  {r.page_title!r}")
        if r.price:
            print(f"  price:       {r.price!r}")
        print()

    return 0


def _run_web_service_mode(
    track: SimpleNamespace,
    *,
    max_results: int,
    trace: bool,
    web_search_provider: WebSearchProvider | None,
) -> int:
    searcher = MultiSiteWebSearcher()
    query, hits = searcher.search(
        artist=track.artist,
        track=track.title,
        max_results=max_results,
        trace=trace,
        web_search_provider=web_search_provider,
    )

    if web_search_provider == "serper":
        mode = "multi-site web search (Serper)"
    elif web_search_provider == "ddg":
        mode = f"multi-site web search (ddgs backend={DDGS_TEXT_BACKEND})"
    elif api_config.USE_SERPER and api_config.SERPER_API_KEY.strip():
        mode = "multi-site web search (Serper, from env USE_SERPER)"
    else:
        mode = f"multi-site web search (ddgs backend={DDGS_TEXT_BACKEND}, from env)"

    print(f"Mode: {mode}")
    print(f"Title:  {track.title!r}")
    print(f"Artist: {track.artist!r}")
    print(f"Query:  {query!r}")
    print(f"Repeat in browser: {multisite_repeat_search_url(query, web_search_provider=web_search_provider)}")
    print(f"max_results: {max_results}")
    print()

    if not hits:
        print("No results (after site + URL filters).")
        return 1

    for i, h in enumerate(hits, start=1):
        print(f"--- #{i}")
        print(f"  url:             {h.url}")
        print(f"  matched_domain: {h.matched_domain}")
        print(f"  title:           {h.title!r}")
        if h.body:
            print(f"  body:            {h.body!r}")
        print()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug Amazon or multi-site web search.")
    parser.add_argument(
        "query_parts",
        nargs="+",
        help='Title and artist words, or use --artist "Name"',
    )
    parser.add_argument(
        "--artist",
        default=None,
        help="Explicit artist; otherwise last query word is treated as artist",
    )
    parser.add_argument(
        "--web-service",
        action="store_true",
        help="Multi-site web search (tidal, amazon, soundcloud + URL filters)",
    )
    ws_engine = parser.add_mutually_exclusive_group()
    ws_engine.add_argument(
        "--serper",
        action="store_true",
        help="With --web-service: use Serper (set SERPER_API_KEY)",
    )
    ws_engine.add_argument(
        "--ddgs",
        action="store_true",
        help="With --web-service: use ddgs (Brave by default), ignore USE_SERPER",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="With --web-service: FILTERED / TRANSFORMED / DEDUPED trace on stderr",
    )
    parser.add_argument(
        "--no-ddg",
        action="store_true",
        help="Amazon HTML search only (Amazon mode only)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        metavar="N",
        help=f"Max results (default: MAX_WEB_RESULTS={MAX_WEB_RESULTS})",
    )
    args = parser.parse_args()
    track = _parse_track_args(args.query_parts, args.artist)
    max_results = MAX_WEB_RESULTS if args.max is None else args.max

    if args.serper or args.ddgs:
        if not args.web_service:
            parser.error("--serper and --ddgs require --web-service")

    if args.web_service:
        if args.verbose:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                stream=sys.stderr,
                force=True,
            )
        web_search_provider: WebSearchProvider | None = None
        if args.serper:
            web_search_provider = "serper"
        elif args.ddgs:
            web_search_provider = "ddg"
        return _run_web_service_mode(
            track,
            max_results=max_results,
            trace=args.verbose,
            web_search_provider=web_search_provider,
        )
    return _run_amazon_mode(track, use_ddg=not args.no_ddg, max_results=max_results)


if __name__ == "__main__":
    raise SystemExit(main())
