"""Spotify OAuth (authorization code + PKCE): token exchange, refresh, DB persistence."""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.config import (
    get_spotify_client_credentials,
    get_spotify_redirect_uri,
)
from track_mapper_api.models.spotify_oauth import SpotifyUserConnection

logger = logging.getLogger(__name__)

ACCOUNTS_URL = "https://accounts.spotify.com/api/token"
ME_URL = "https://api.spotify.com/v1/me"

# No playlist-read-public — not a valid Spotify scope (see developer.spotify.com scopes).
SPOTIFY_AUTH_SCOPES = "playlist-read-private playlist-read-collaborative"


class SpotifyNotConnectedError(Exception):
    """No Spotify account linked for this user (connect via OAuth first)."""


def spotify_authorize_scopes() -> str:
    return SPOTIFY_AUTH_SCOPES.strip().replace(" ", " ")


def exchange_authorization_code(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict:
    """Trade auth code + PKCE verifier for tokens (sync HTTP)."""
    client_id, client_secret = get_spotify_client_credentials()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        ACCOUNTS_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        logger.warning(
            "Spotify OAuth code exchange failed: status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )
        raise RuntimeError(
            "Spotify refused the authorization code (expired session or wrong redirect URI).",
        )
    body = resp.json()
    if not body.get("refresh_token") or not body.get("access_token"):
        raise RuntimeError("Spotify token response missing refresh_token or access_token.")
    return body


def refresh_access_token(*, refresh_token: str) -> dict:
    client_id, client_secret = get_spotify_client_credentials()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        ACCOUNTS_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        logger.warning(
            "Spotify token refresh failed: status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )
        raise RuntimeError("Spotify refresh token invalid or expired; connect again.")
    body = resp.json()
    if not body.get("access_token"):
        raise RuntimeError("Spotify refresh response missing access_token.")
    return body


def fetch_spotify_profile_id(access_token: str) -> str | None:
    r = requests.get(
        ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    data = r.json()
    sid = data.get("id")
    return sid if isinstance(sid, str) and sid else None


async def upsert_connection(
    db: AsyncSession,
    *,
    user_id: str,
    refresh_token: str,
    access_token: str,
    expires_in: int,
    scope: str | None,
    spotify_user_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    safe_expires = max(120, int(expires_in))
    access_expires_at = now + timedelta(seconds=safe_expires - 60)
    res = await db.execute(
        select(SpotifyUserConnection).where(SpotifyUserConnection.user_id == user_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = SpotifyUserConnection(
            user_id=user_id,
            refresh_token=refresh_token,
            access_token=access_token,
            access_expires_at=access_expires_at,
            spotify_user_id=spotify_user_id,
            scope=scope,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.refresh_token = refresh_token
        row.access_token = access_token
        row.access_expires_at = access_expires_at
        if spotify_user_id:
            row.spotify_user_id = spotify_user_id
        if scope:
            row.scope = scope
        row.updated_at = now
    await db.flush()


async def delete_connection(db: AsyncSession, *, user_id: str) -> bool:
    r = await db.execute(
        delete(SpotifyUserConnection).where(SpotifyUserConnection.user_id == user_id)
    )
    await db.flush()
    return (r.rowcount or 0) > 0


async def get_spotify_user_access_token(db: AsyncSession, *, user_id: str) -> str | None:
    """Return a valid access token, refreshing if needed. ``None`` if not connected."""
    res = await db.execute(
        select(SpotifyUserConnection).where(SpotifyUserConnection.user_id == user_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    if row.access_expires_at > now:
        return row.access_token

    try:
        body = await asyncio.to_thread(refresh_access_token, refresh_token=row.refresh_token)
    except RuntimeError:
        logger.exception("Spotify refresh failed for user_id=%s", user_id)
        await delete_connection(db, user_id=user_id)
        return None

    new_access = body["access_token"]
    expires_in = body.get("expires_in")
    if not isinstance(expires_in, int):
        expires_in = 3600
    new_refresh = body.get("refresh_token") or row.refresh_token

    await upsert_connection(
        db,
        user_id=user_id,
        refresh_token=new_refresh,
        access_token=new_access,
        expires_in=expires_in,
        scope=row.scope,
        spotify_user_id=row.spotify_user_id,
    )
    return new_access


async def is_spotify_connected(db: AsyncSession, *, user_id: str) -> tuple[bool, str | None]:
    res = await db.execute(
        select(SpotifyUserConnection).where(SpotifyUserConnection.user_id == user_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return False, None
    return True, row.spotify_user_id
