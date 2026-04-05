"""Import a Spotify playlist via Web API (user OAuth access token)."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.config import get_spotify_market
from track_mapper_api.services.playlist_import import PlaylistTrackInput, import_playlist_tracks
from track_mapper_api.services.spotify_oauth_service import (
    SpotifyNotConnectedError,
    get_spotify_user_access_token,
)
from track_mapper_api.services.spotify_web_api import (
    fetch_playlist_tracks,
    parse_spotify_playlist_id,
)


async def import_public_spotify_playlist(
    db: AsyncSession,
    *,
    user_id: str,
    playlist_id_or_url: str,
    playlist_name_override: str | None = None,
) -> tuple[uuid.UUID, int, int]:
    playlist_id = parse_spotify_playlist_id(playlist_id_or_url)
    access = await get_spotify_user_access_token(db, user_id=user_id)
    if access is None:
        raise SpotifyNotConnectedError(
            "Connect Spotify in the workspace header (OAuth), then try importing again.",
        )

    bundle = await asyncio.to_thread(
        fetch_playlist_tracks,
        access,
        playlist_id,
        market=get_spotify_market(),
    )

    if playlist_name_override and playlist_name_override.strip():
        display_name = playlist_name_override.strip()
    elif bundle.playlist_name:
        display_name = bundle.playlist_name
    else:
        display_name = f"Spotify playlist {playlist_id}"

    tracks = [
        PlaylistTrackInput(
            title=row.title,
            artist=row.artist,
            album=row.album,
            duration_ms=row.duration_ms,
            spotify_id=row.spotify_id,
        )
        for row in bundle.tracks
    ]

    return await import_playlist_tracks(
        db,
        user_id=user_id,
        name=display_name,
        tracks=tracks,
        import_source="spotify_web_api",
        source_kind="spotify_web_api",
    )
