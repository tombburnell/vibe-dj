from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.config import get_spotify_client_id_public, get_spotify_redirect_uri
from track_mapper_api.deps import get_current_user_id, get_db
from track_mapper_api.schemas import (
    SpotifyOAuthConfigOut,
    SpotifyOAuthStatusOut,
    SpotifyOAuthTokenIn,
    SpotifyOAuthTokenOut,
)
from track_mapper_api.services.spotify_oauth_service import (
    delete_connection,
    exchange_authorization_code,
    fetch_spotify_profile_id,
    is_spotify_connected,
    upsert_connection,
)

router = APIRouter(prefix="/integrations/spotify", tags=["spotify"])


@router.get("/oauth/config", response_model=SpotifyOAuthConfigOut)
async def spotify_oauth_config() -> SpotifyOAuthConfigOut:
    """Public values for building the browser authorize URL (no VITE_ env required)."""
    try:
        client_id = get_spotify_client_id_public()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return SpotifyOAuthConfigOut(
        client_id=client_id,
        redirect_uri=get_spotify_redirect_uri().strip(),
    )


@router.get("/oauth/status", response_model=SpotifyOAuthStatusOut)
async def spotify_oauth_status(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SpotifyOAuthStatusOut:
    connected, sid = await is_spotify_connected(db, user_id=user_id)
    return SpotifyOAuthStatusOut(connected=connected, spotify_user_id=sid)


@router.post("/oauth/token", response_model=SpotifyOAuthTokenOut)
async def spotify_oauth_token(
    body: SpotifyOAuthTokenIn,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SpotifyOAuthTokenOut:
    expected = get_spotify_redirect_uri().strip()
    if body.redirect_uri.strip() != expected:
        raise HTTPException(
            status_code=400,
            detail="redirect_uri must match the API configuration (SPOTIFY_REDIRECT_URI).",
        )
    try:
        tokens = exchange_authorization_code(
            code=body.code.strip(),
            code_verifier=body.code_verifier.strip(),
            redirect_uri=body.redirect_uri.strip(),
        )
    except RuntimeError as e:
        msg = str(e)
        status = 503 if "SPOTIFY_CLIENT_ID" in msg or "SPOTIFY_CLIENT_SECRET" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from e

    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    expires_in = tokens.get("expires_in")
    if not isinstance(expires_in, int):
        expires_in = 3600
    scope = tokens.get("scope")
    scope_str = scope if isinstance(scope, str) else None

    spotify_user_id = await asyncio.to_thread(fetch_spotify_profile_id, access)

    await upsert_connection(
        db,
        user_id=user_id,
        refresh_token=refresh,
        access_token=access,
        expires_in=expires_in,
        scope=scope_str,
        spotify_user_id=spotify_user_id,
    )
    return SpotifyOAuthTokenOut()


@router.delete("/oauth/disconnect", status_code=204)
async def spotify_oauth_disconnect(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Response:
    await delete_connection(db, user_id=user_id)
    return Response(status_code=204)
