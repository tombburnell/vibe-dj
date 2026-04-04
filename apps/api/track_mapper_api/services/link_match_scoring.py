"""Fuzzy match scores for link-search results (RapidFuzz token_sort_ratio, 0–100)."""

from __future__ import annotations

from typing import Protocol


class _SnippetLike(Protocol):
    title: str
    body: str


def match_query_for_track(artist: str, track: str) -> str:
    """Same quoted form used for Amazon DDG matching: ``"artist" "title"``."""
    a = (artist or "").strip()
    t = (track or "").strip()
    return f'"{a}" "{t}"'


def score_token_sort(text: str, query: str) -> float:
    """``token_sort_ratio`` on normalized whitespace; empty inputs → 0."""
    from rapidfuzz import fuzz

    t = " ".join((text or "").lower().split())
    q = " ".join((query or "").lower().split())
    if not t or not q:
        return 0.0
    return float(fuzz.token_sort_ratio(t, q))


def score_artist_title_against_query(artist: str, title: str, query: str) -> float:
    """Score ``"{artist} {title}"`` against ``query`` (e.g. Amazon HTML search string)."""
    blob = f"{(artist or '').strip()} {(title or '').strip()}".strip()
    return score_token_sort(blob, query)


def score_web_hit_snippet(hit: _SnippetLike, match_query: str) -> float:
    """Score SERP title + body against the quoted track query."""
    blob = f"{(hit.title or '').strip()} {(hit.body or '').strip()}".strip()
    return score_token_sort(blob, match_query)
