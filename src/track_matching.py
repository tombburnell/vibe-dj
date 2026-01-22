from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from .track_normalizer import create_base_title, extract_artist_tokens, normalize_text


ARTIST_STOPWORDS = {
    "and",
    "feat",
    "ft",
    "featuring",
    "with",
    "vs",
    "x",
    # keep "the"
}

TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "of",
    "from",
    "at",
    "in",
    "on",
    "for",
    "to",
}

VARIATION_KEYWORDS = {
    "remix",
    "mix",
    "edit",
    "version",
    "dub",
    "rework",
    "re-edit",
    "bootleg",
    "live",
    "acoustic",
    "instrumental",
    "radio",
    "extended",
    "remaster",
    "mono",
    "stereo",
    "demo",
    "karaoke",
    "cover",
    "session",
    "vip",
}

TITLE_WEIGHT = 0.6
ARTIST_WEIGHT = 0.4

DURATION_WEIGHT = 0.1
DURATION_MULTIPLIER = 1.5

TOKEN_MATCH_THRESHOLD = 0.85

TITLE_ORDER_WEIGHT = 0.3
TITLE_TOKEN_WEIGHT = 0.7

PRIMARY_ARTIST_WEIGHT = 0.8
EXTRA_ARTIST_WEIGHT = 0.2

TOKEN_LENGTH_MIN = 3
TOKEN_LENGTH_RATIO_MIN = 0.8
TOKEN_LENGTH_RATIO_MAX = 1.25
TOKEN_PREFIX_PENALTY = 0.3

VARIATION_WEIGHT = 0.2
MISSING_WORDS_WEIGHT = 0.1


@dataclass
class TokenMatchDetail:
    token: str
    weight: float
    best_match: str | None
    score: float


def _tapered_weights(tokens: list[str]) -> list[float]:
    """Create tapered weights based on token importance."""
    if not tokens:
        return []
    if len(tokens) == 1:
        return [1.0]
    base = list(range(len(tokens), 0, -1))
    total = sum(base)
    return [b / total for b in base]


def _tokenize_artist(artist: str) -> list[str]:
    """Tokenize artist name and drop stopwords (except 'the')."""
    tokens: list[str] = []
    for token in extract_artist_tokens(artist):
        for word in normalize_text(token).split():
            if word and word not in ARTIST_STOPWORDS:
                tokens.append(word)
    return tokens


def _split_artist_groups(artist: str) -> list[str]:
    """Split artist string into groups, preserving multi-word names."""
    import re

    if not artist:
        return []
    text = normalize_text(artist)
    parts = re.split(
        r"\s+feat\s+|\s+ft\s+|\s+featuring\s+|\s+and\s+|,|;|&",
        text,
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if p and p.strip()]


def _extract_primary_artist_tokens(artist: str) -> tuple[list[str], list[str]]:
    """Return (primary_tokens, extra_tokens) based on artist groups."""
    groups = _split_artist_groups(artist)
    if not groups:
        return ([], [])
    primary_group = groups[0]
    extra_groups = groups[1:]
    primary_tokens = [t for t in normalize_text(primary_group).split() if t]
    extra_tokens: list[str] = []
    for group in extra_groups:
        extra_tokens.extend([t for t in normalize_text(group).split() if t])
    primary_tokens = [t for t in primary_tokens if t not in ARTIST_STOPWORDS]
    extra_tokens = [t for t in extra_tokens if t not in ARTIST_STOPWORDS]
    return (primary_tokens, extra_tokens)


def _tokenize_artist_tokens(tokens: list[str]) -> list[str]:
    """Tokenize artist tokens (Rekordbox side)."""
    words: list[str] = []
    for token in tokens:
        for word in normalize_text(token).split():
            if word and word not in ARTIST_STOPWORDS:
                words.append(word)
    return words


def _is_id_token(token: str) -> bool:
    """Detect release codes or IDs that should not influence title matching."""
    import re

    if not token:
        return False
    if token.isdigit() and len(token) >= 2:
        return True
    if re.match(r"^[A-Z]{2,}\d+$", token):
        return True
    if re.match(r"^[A-Z0-9]{4,}$", token) and any(c.isdigit() for c in token):
        return True
    if re.match(r"^B0[0-9A-Z]{8,}$", token):
        return True
    return False


def _extract_variation_tokens(title: str) -> list[str]:
    """Extract variation tokens from title, including parenthetical/dash segments."""
    import re

    if not title:
        return []

    title_lower = title.lower()
    tokens = [t for t in normalize_text(title_lower).split() if t]
    variation_tokens: list[str] = []

    # Keywords present in full title
    for token in tokens:
        if token in VARIATION_KEYWORDS:
            variation_tokens.append(token)

    # Parenthetical and bracketed segments
    segments = []
    segments.extend(re.findall(r"\(([^)]*)\)", title_lower))
    segments.extend(re.findall(r"\[([^\]]*)\]", title_lower))

    # Dash suffix (often used for versions)
    if " - " in title_lower:
        parts = title_lower.split(" - ", 1)
        if len(parts) == 2:
            segments.append(parts[1])

    for segment in segments:
        seg_tokens = [t for t in normalize_text(segment).split() if t]
        for token in seg_tokens:
            if token in TITLE_STOPWORDS:
                continue
            if _is_id_token(token):
                continue
            variation_tokens.append(token)

    # De-dupe while preserving order
    seen = set()
    result = []
    for token in variation_tokens:
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result


def _filter_title_tokens(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Filter title tokens by removing stopwords, variation keywords, and IDs."""
    filtered = []
    removed = []
    for token in tokens:
        if token in TITLE_STOPWORDS or token in VARIATION_KEYWORDS or _is_id_token(token):
            removed.append(token)
            continue
        filtered.append(token)
    return filtered, removed


def _token_similarity(token: str, candidate: str) -> float:
    """Token similarity with length and prefix penalties."""
    if not token or not candidate:
        return 0.0
    if len(token) < TOKEN_LENGTH_MIN or len(candidate) < TOKEN_LENGTH_MIN:
        return 1.0 if token == candidate else 0.0

    score = fuzz.ratio(token, candidate) / 100.0

    length_ratio = min(len(token), len(candidate)) / max(len(token), len(candidate))
    if length_ratio < TOKEN_LENGTH_RATIO_MIN or length_ratio > TOKEN_LENGTH_RATIO_MAX:
        score *= 0.4

    if token[:2] != candidate[:2]:
        score *= TOKEN_PREFIX_PENALTY

    return score


def _best_token_match_score(token: str, candidates: list[str]) -> tuple[float, str | None]:
    """Return best fuzzy match score (0-1) and matching token."""
    best_score = 0.0
    best_token = None
    for cand in candidates:
        score = _token_similarity(token, cand)
        if score > best_score:
            best_score = score
            best_token = cand
    return (best_score, best_token)


def _weighted_token_score(
    source_tokens: list[str], target_tokens: list[str]
) -> tuple[float, float, float, list[TokenMatchDetail]]:
    """Compute weighted coverage + quality for tokens."""
    if not source_tokens or not target_tokens:
        return (0.0, 0.0, 0.0, [])

    ordered = sorted(source_tokens, key=len, reverse=True)
    weights = _tapered_weights(ordered)

    details: list[TokenMatchDetail] = []
    coverage = 0.0
    quality = 0.0

    for token, weight in zip(ordered, weights):
        score, best_match = _best_token_match_score(token, target_tokens)
        details.append(
            TokenMatchDetail(
                token=token,
                weight=weight,
                best_match=best_match,
                score=score,
            )
        )
        if score >= TOKEN_MATCH_THRESHOLD:
            coverage += weight
        quality += weight * score

    combined = (coverage * 0.6) + (quality * 0.4)
    return (coverage, quality, combined, details)


def _title_score(title_a: str, title_b: str) -> tuple[float, dict[str, Any]]:
    """Title score based on token coverage + quality on base titles."""
    base_a = create_base_title(title_a)
    base_b = create_base_title(title_b)
    raw_tokens_a = [t for t in normalize_text(base_a).split() if t]
    raw_tokens_b = [t for t in normalize_text(base_b).split() if t]
    tokens_a, removed_a = _filter_title_tokens(raw_tokens_a)
    tokens_b, removed_b = _filter_title_tokens(raw_tokens_b)

    coverage, quality, combined, details = _weighted_token_score(tokens_a, tokens_b)
    order_score = fuzz.ratio(normalize_text(base_a), normalize_text(base_b)) / 100.0
    final_title_score = (combined * TITLE_TOKEN_WEIGHT) + (order_score * TITLE_ORDER_WEIGHT)

    debug = {
        "title_a_base": base_a,
        "title_b_base": base_b,
        "tokens_a": tokens_a,
        "tokens_b": tokens_b,
        "removed_tokens_a": removed_a,
        "removed_tokens_b": removed_b,
        "coverage": coverage,
        "quality": quality,
        "order_score": order_score,
        "details": details,
    }
    return final_title_score, debug


def _artist_score(spotify_artist: str, rb_artist_tokens: list[str]) -> tuple[float, dict[str, Any]]:
    """Artist score using token-level matching with tapered weights."""
    primary_tokens, extra_tokens = _extract_primary_artist_tokens(spotify_artist)
    rb_tokens = _tokenize_artist_tokens(rb_artist_tokens)

    primary_coverage, primary_quality, primary_combined, primary_details = _weighted_token_score(
        primary_tokens, rb_tokens
    )
    extra_coverage, extra_quality, extra_combined, extra_details = _weighted_token_score(
        extra_tokens, rb_tokens
    )

    combined = (primary_combined * PRIMARY_ARTIST_WEIGHT) + (
        extra_combined * EXTRA_ARTIST_WEIGHT
    )

    debug = {
        "primary_tokens": primary_tokens,
        "extra_tokens": extra_tokens,
        "rekordbox_tokens": rb_tokens,
        "primary_coverage": primary_coverage,
        "primary_quality": primary_quality,
        "primary_details": primary_details,
        "extra_coverage": extra_coverage,
        "extra_quality": extra_quality,
        "extra_details": extra_details,
    }
    return combined, debug


def _duration_score(ms_a: int | None, ms_b: int | None) -> tuple[float, dict[str, Any]]:
    """Duration score based on percentage difference."""
    if not ms_a or not ms_b:
        return (0.5, {"diff_ratio": None, "score": 0.5})

    diff = abs(ms_a - ms_b)
    max_ms = max(ms_a, ms_b)
    diff_ratio = diff / max_ms

    score = max(0.0, 1.0 - (diff_ratio * DURATION_MULTIPLIER))
    return (score, {"diff_ratio": diff_ratio, "score": score})


def calculate_match_score(
    library_track,
    rekordbox_track,
    return_debug: bool = False,
) -> float | tuple[float, dict[str, Any]]:
    """Unified match score (0-1) with optional debug."""
    title_score, title_debug = _title_score(library_track.title, rekordbox_track.title)
    artist_score, artist_debug = _artist_score(
        library_track.artist, rekordbox_track.artist_tokens
    )
    duration_score, duration_debug = _duration_score(
        library_track.duration_ms, rekordbox_track.duration_ms
    )

    variation_tokens_a = _extract_variation_tokens(library_track.title)
    variation_tokens_b = _extract_variation_tokens(rekordbox_track.title)
    variation_overlap = sorted(set(variation_tokens_a) & set(variation_tokens_b))
    if variation_tokens_a or variation_tokens_b:
        if variation_tokens_a and variation_tokens_b:
            coverage_a = len(variation_overlap) / len(variation_tokens_a) if variation_tokens_a else 0.0
            coverage_b = len(variation_overlap) / len(variation_tokens_b) if variation_tokens_b else 0.0
            variation_match = (coverage_a + coverage_b) / 2.0
        else:
            variation_match = 0.0
    else:
        variation_match = 1.0

    variation_penalty = (1.0 - variation_match) * VARIATION_WEIGHT

    missing_a = [t for t in title_debug["tokens_a"] if t not in title_debug["tokens_b"]]
    missing_b = [t for t in title_debug["tokens_b"] if t not in title_debug["tokens_a"]]
    total_title_tokens = len(title_debug["tokens_a"]) + len(title_debug["tokens_b"])
    missing_ratio = (len(missing_a) + len(missing_b)) / max(total_title_tokens, 1)
    missing_penalty = missing_ratio * MISSING_WORDS_WEIGHT

    text_score = (title_score * TITLE_WEIGHT) + (artist_score * ARTIST_WEIGHT)
    final_score = (text_score * (1.0 - DURATION_WEIGHT)) + (
        duration_score * DURATION_WEIGHT
    )
    final_score = final_score - variation_penalty - missing_penalty

    final_score = min(1.0, max(0.0, final_score))

    if return_debug:
        return (
            final_score,
            {
                "title_score": title_score,
                "artist_score": artist_score,
                "duration_score": duration_score,
                "text_score": text_score,
                "variation_penalty": variation_penalty,
                "missing_penalty": missing_penalty,
                "final_score": final_score,
                "title_debug": title_debug,
                "artist_debug": artist_debug,
                "duration_debug": duration_debug,
                "variation_debug": {
                    "tokens_a": variation_tokens_a,
                    "tokens_b": variation_tokens_b,
                    "overlap": variation_overlap,
                    "match": variation_match,
                },
                "missing_debug": {
                    "missing_a": missing_a,
                    "missing_b": missing_b,
                    "missing_ratio": missing_ratio,
                },
            },
        )

    return final_score
