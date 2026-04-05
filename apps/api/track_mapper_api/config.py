from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_API_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _API_ROOT / ".env"
# Tests set ``TRACKMAPPER_SKIP_DOTENV=1`` in ``conftest`` so a developer ``.env`` (e.g. USE_SERPER)
# does not override stubbed search clients.
_skip_dotenv = os.environ.get("TRACKMAPPER_SKIP_DOTENV", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
if _ENV_FILE.is_file() and not _skip_dotenv:
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.debug(
            "python-dotenv not installed; skipping %s (install python-dotenv or set env in shell)",
            _ENV_FILE,
        )
    else:
        load_dotenv(_ENV_FILE, override=False)


def _truthy_env(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _positive_int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r (not an integer); using default %s", name, raw, default)
        return default
    if value < 1:
        logger.warning("Invalid %s=%r (must be >= 1); using default %s", name, raw, default)
        return default
    return value


# Default cap for web/DDG search results; override with MAX_WEB_RESULTS (positive int).
# Resolved when this module is first imported (restart process to pick up env changes).
MAX_WEB_RESULTS: int = _positive_int_from_env("MAX_WEB_RESULTS", 10)

# Multi-site web search: Serper (google.serper.dev) vs local ``ddgs`` package.
USE_SERPER: bool = _truthy_env("USE_SERPER", default=False)
SERPER_API_KEY: str = os.environ.get("SERPER_API_KEY", "").strip()


@lru_cache
def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: postgresql+psycopg://user:pass@localhost:5432/trackmapper",
        )
    return url


def clear_config_cache() -> None:
    get_database_url.cache_clear()


def get_dev_user_id() -> str:
    return os.environ.get("DEV_USER_ID", "dev-user").strip() or "dev-user"


def get_spotify_client_credentials() -> tuple[str, str]:
    """Client id + secret for Spotify Web API (client-credentials flow).

    ``SPOTIFY_SECRET_KEY`` is accepted as an alias for the client secret for
    older local env files.
    """
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = (
        os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
        or os.environ.get("SPOTIFY_SECRET_KEY", "").strip()
    )
    if not client_id or not client_secret:
        raise RuntimeError(
            "Spotify import requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
            "(or SPOTIFY_SECRET_KEY) in the API environment.",
        )
    logger.info(
        "Spotify client credentials resolved (prefixes only): client_id=%s... secret=%s...",
        client_id[:4],
        client_secret[:4],
    )
    return client_id, client_secret


def get_spotify_market() -> str:
    """ISO 3166-1 alpha-2 country for Spotify Web API ``market`` (client-credentials playlists)."""
    raw = os.environ.get("SPOTIFY_MARKET", "US").strip().upper()
    if len(raw) == 2 and raw.isalpha():
        resolved = raw
    else:
        if raw:
            logger.warning(
                "Invalid SPOTIFY_MARKET=%r (want two letters, e.g. US); using US",
                os.environ.get("SPOTIFY_MARKET", ""),
            )
        resolved = "US"
    logger.info("Spotify market resolved: %s", resolved)
    return resolved


def get_spotify_redirect_uri() -> str:
    """OAuth redirect URI; must match Spotify app settings exactly (and token exchange body)."""
    raw = os.environ.get("SPOTIFY_REDIRECT_URI", "").strip()
    if raw:
        return raw
    return "http://127.0.0.1:5173/spotify-callback"


def get_spotify_client_id_public() -> str:
    """Public OAuth client id only (no logging; does not require client secret)."""
    cid = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    if not cid:
        raise RuntimeError("SPOTIFY_CLIENT_ID is not set in the API environment.")
    return cid
