"""Spotify Web API: playlist fetch with a bearer access token (user OAuth or client credentials)."""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

ACCOUNTS_URL = "https://accounts.spotify.com/api/token"


def _log_spotify_response_json(label: str, payload: object) -> None:
    """Pretty-print Spotify API JSON for import debugging (can be large)."""
    try:
        pretty = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        pretty = str(payload)
    logger.info("Spotify Web API response %s:\n%s", label, pretty)


API_BASE = "https://api.spotify.com/v1"


def _log_first_track_from_tracks_endpoint(
    *,
    headers: dict[str, str],
    track_id: str,
    market: str,
) -> None:
    """GET ``/v1/tracks/{id}`` for the first playlist track (compare vs playlist-embedded object)."""
    tid = track_id.strip()
    if not tid:
        return
    m = market.strip().upper()
    if len(m) != 2:
        m = "US"
    url = f"{API_BASE}/tracks/{tid}"
    resp = requests.get(url, headers=headers, params={"market": m}, timeout=60)
    if resp.status_code != 200:
        logger.warning(
            "Spotify GET /v1/tracks/%s failed: status=%s body=%s",
            tid,
            resp.status_code,
            resp.text[:500],
        )
        return
    try:
        body = resp.json()
    except ValueError:
        logger.warning("Spotify GET /v1/tracks/%s: response was not JSON", tid)
        return
    _log_spotify_response_json(f"GET /v1/tracks/{tid} (market={m})", body)


# Spotify playlist ids are base62; URLs may include locale segments before ``playlist/``.
_PLAYLIST_URL_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?playlist/([a-zA-Z0-9]{22})\b",
    re.IGNORECASE,
)
_SPOTIFY_URI_RE = re.compile(r"^spotify:playlist:([a-zA-Z0-9]{22})\s*$", re.IGNORECASE)
_RAW_ID_RE = re.compile(r"^[a-zA-Z0-9]{22}\s*$")


class SpotifyPlaylistParseError(ValueError):
    """User input is not a valid Spotify playlist URL, URI, or id."""


class SpotifyWebApiError(Exception):
    """Spotify HTTP/API failure (do not subclass RuntimeError: routers catch RuntimeError for config)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class SpotifyPlaylistBundle:
    playlist_name: str | None
    tracks: list["SpotifyTrackRow"]


@dataclass(frozen=True)
class SpotifyTrackRow:
    spotify_id: str
    title: str
    artist: str
    album: str | None
    duration_ms: int | None


@dataclass
class _AccessTokenCache:
    token: str
    expires_at: float


_token_cache: _AccessTokenCache | None = None


def parse_spotify_playlist_id(raw: str) -> str:
    s = raw.strip()
    if not s:
        raise SpotifyPlaylistParseError("Playlist URL or id is empty.")
    m = _SPOTIFY_URI_RE.match(s)
    if m:
        return m.group(1)
    m = _PLAYLIST_URL_RE.search(s)
    if m:
        return m.group(1)
    if _RAW_ID_RE.match(s):
        return s.strip()
    raise SpotifyPlaylistParseError(
        "Expected a Spotify playlist URL, spotify:playlist:… URI, or 22-character playlist id.",
    )


def _get_access_token(client_id: str, client_secret: str) -> str:
    global _token_cache
    now = time.monotonic()
    if _token_cache is not None and now < _token_cache.expires_at:
        return _token_cache.token

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        ACCOUNTS_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if resp.status_code != 200:
        logger.warning(
            "Spotify token request failed: status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )
        raise SpotifyWebApiError(
            "Could not obtain Spotify access token (check client id and secret).",
            status_code=resp.status_code,
        )
    body = resp.json()
    token = body.get("access_token")
    expires_in = body.get("expires_in")
    if not token or not isinstance(expires_in, int):
        raise SpotifyWebApiError("Spotify token response was missing access_token or expires_in.")
    # Refresh slightly early to avoid edge-of-expiry failures.
    _token_cache = _AccessTokenCache(
        token=token,
        expires_at=now + max(60, expires_in - 120),
    )
    return token


def _row_from_track_item(track_obj: dict | None) -> SpotifyTrackRow | None:
    if not track_obj or not isinstance(track_obj, dict):
        return None
    if track_obj.get("is_local"):
        return None
    if track_obj.get("type") != "track":
        return None
    tid = track_obj.get("id")
    if not tid or not isinstance(tid, str):
        return None
    title = (track_obj.get("name") or "").strip()
    artists_raw = track_obj.get("artists")
    artist_parts: list[str] = []
    if isinstance(artists_raw, list):
        for a in artists_raw:
            if isinstance(a, dict):
                n = (a.get("name") or "").strip()
                if n:
                    artist_parts.append(n)
    artist = ", ".join(artist_parts)
    album_name = None
    album = track_obj.get("album")
    if isinstance(album, dict):
        album_name = (album.get("name") or "").strip() or None
    duration_ms = track_obj.get("duration_ms")
    dur: int | None = None
    if isinstance(duration_ms, int) and duration_ms > 0:
        dur = duration_ms
    if not title and not artist:
        return None
    return SpotifyTrackRow(
        spotify_id=tid,
        title=title or "Unknown Title",
        artist=artist or "Unknown Artist",
        album=album_name,
        duration_ms=dur,
    )


def _playlist_tracks_path_to_items(path: str) -> str:
    """Feb 2026 API: ``GET .../playlists/{id}/tracks`` → ``.../items`` (migration guide)."""
    if path.endswith("/tracks"):
        return path[: -len("/tracks")] + "/items"
    return path


def _normalize_playlist_items_list_url(url: str) -> str:
    """Rewrite deprecated ``/tracks`` pagination URLs to ``/items``."""
    parts = urlparse(url)
    new_path = _playlist_tracks_path_to_items(parts.path)
    if new_path == parts.path:
        return url
    return urlunparse((parts.scheme, parts.netloc, new_path, parts.params, parts.query, parts.fragment))


def _ensure_playlist_items_page_url(url: str, market: str) -> str:
    """Merge ``market`` and ``additional_types=track`` (episodes + client creds → 403)."""
    url = _normalize_playlist_items_list_url(url)
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "market" not in q:
        q["market"] = market
    q["additional_types"] = "track"
    new_query = urlencode(list(q.items()))
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))


def _playlist_embedded_items_block(pl_json: dict) -> dict | None:
    """Paging object under ``items`` (post–Feb 2026) or legacy ``tracks`` on Get Playlist."""
    items_block = pl_json.get("items")
    if isinstance(items_block, dict) and isinstance(items_block.get("items"), list):
        return items_block
    tracks_block = pl_json.get("tracks")
    if isinstance(tracks_block, dict) and isinstance(tracks_block.get("items"), list):
        return tracks_block
    return None


def fetch_playlist_tracks(
    access_token: str,
    playlist_id: str,
    *,
    market: str,
) -> SpotifyPlaylistBundle:
    """Fetch playlist metadata and tracks using any valid Spotify access token."""
    headers = {"Authorization": f"Bearer {access_token}"}
    m = market.strip().upper()
    if len(m) != 2:
        m = "US"
    market_q = f"?market={m}&additional_types=track"

    pl_resp = requests.get(
        f"{API_BASE}/playlists/{playlist_id}{market_q}",
        headers=headers,
        timeout=30,
    )
    if pl_resp.status_code == 404:
        raise SpotifyWebApiError(
            "Playlist not found or not accessible (public playlists only without user login).",
            status_code=404,
        )
    if pl_resp.status_code != 200:
        logger.warning(
            "Spotify playlist metadata failed: status=%s id=%s body=%s",
            pl_resp.status_code,
            playlist_id,
            pl_resp.text[:500],
        )
        raise SpotifyWebApiError(
            "Spotify rejected the playlist request.",
            status_code=pl_resp.status_code,
        )
    pl_json = pl_resp.json()
    pl_name = pl_json.get("name")
    playlist_name = pl_name.strip() if isinstance(pl_name, str) and pl_name.strip() else None

    tracks: list[SpotifyTrackRow] = []

    def _append_rows_from_page(page: dict) -> None:
        items = page.get("items")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            tobj = item.get("track")
            if tobj is None:
                tobj = item.get("item")
            row = _row_from_track_item(tobj)
            if row is not None:
                tracks.append(row)

    embedded = _playlist_embedded_items_block(pl_json)
    url: str | None = None
    if embedded is not None:
        _append_rows_from_page(embedded)
        nxt = embedded.get("next")
        url = nxt if isinstance(nxt, str) and nxt.strip() else None

    if url is None and not tracks and embedded is None:
        # No embedded page (common for playlists you do not own after Feb 2026).
        url = _ensure_playlist_items_page_url(
            f"{API_BASE}/playlists/{playlist_id}/items?limit=50&market={m}",
            m,
        )

    page_index = 0
    while url:
        page_url = _ensure_playlist_items_page_url(url, m)
        tr_resp = requests.get(page_url, headers=headers, timeout=60)
        if tr_resp.status_code != 200:
            logger.warning(
                "Spotify playlist items page failed: status=%s body=%s",
                tr_resp.status_code,
                tr_resp.text[:500],
            )
            detail = "Spotify rejected a playlist items request."
            if tr_resp.status_code == 403:
                detail = (
                    "Spotify returned 403: under current Web API rules, listing playlist "
                    "tracks usually requires a user access token for the playlist owner or a "
                    "collaborator (client-credentials alone is often rejected). Request "
                    "Extended Quota Mode if eligible, add users in the Developer Dashboard, "
                    "or implement OAuth. See: "
                    "https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide"
                )
            raise SpotifyWebApiError(detail, status_code=tr_resp.status_code)
        page = tr_resp.json()
        # _log_spotify_response_json(
        #     f"GET playlist items page page_index={page_index} playlist_id={playlist_id}",
        #     page,
        # )
        page_index += 1
        _append_rows_from_page(page)
        next_url = page.get("next")
        url = next_url if isinstance(next_url, str) and next_url.strip() else None

    # if tracks:
    #     _log_first_track_from_tracks_endpoint(
    #         headers=headers,
    #         track_id=tracks[0].spotify_id,
    #         market=m,
    #     )

    return SpotifyPlaylistBundle(playlist_name=playlist_name, tracks=tracks)


def fetch_public_playlist_tracks(
    client_id: str,
    client_secret: str,
    playlist_id: str,
    *,
    market: str,
) -> SpotifyPlaylistBundle:
    """Playlist fetch via client-credentials (often 403 on items in Development Mode)."""
    token = _get_access_token(client_id, client_secret)
    return fetch_playlist_tracks(token, playlist_id, market=market)
