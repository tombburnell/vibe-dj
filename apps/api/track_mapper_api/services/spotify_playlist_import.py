"""Import a Spotify playlist via Web API (user OAuth access token)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.playlist import Playlist
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


@dataclass(frozen=True)
class SpotifyPlaylistImportResult:
    playlist_id: uuid.UUID
    playlist_name: str
    track_count: int
    rows_linked: int
    new_source_tracks: int


async def _import_spotify_playlist(
    db: AsyncSession,
    *,
    user_id: str,
    playlist_id_or_url: str,
    playlist_name_override: str | None = None,
) -> SpotifyPlaylistImportResult:
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

    raw_ref = playlist_id_or_url.strip()
    playlist_ref = raw_ref or playlist_id
    playlist_url = raw_ref if "open.spotify.com/" in raw_ref.lower() else None
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

    playlist_row_id, linked, new_src = await import_playlist_tracks(
        db,
        user_id=user_id,
        name=display_name,
        tracks=tracks,
        import_source="spotify_web_api",
        source_kind="spotify_web_api",
        spotify_playlist_id=playlist_id,
        spotify_playlist_url=playlist_url,
    )
    return SpotifyPlaylistImportResult(
        playlist_id=playlist_row_id,
        playlist_name=display_name,
        track_count=len(tracks),
        rows_linked=linked,
        new_source_tracks=new_src,
    )


async def import_public_spotify_playlist(
    db: AsyncSession,
    *,
    user_id: str,
    playlist_id_or_url: str,
    playlist_name_override: str | None = None,
) -> SpotifyPlaylistImportResult:
    return await _import_spotify_playlist(
        db,
        user_id=user_id,
        playlist_id_or_url=playlist_id_or_url,
        playlist_name_override=playlist_name_override,
    )


async def sync_saved_spotify_playlist(
    db: AsyncSession,
    *,
    user_id: str,
    playlist: Playlist,
) -> SpotifyPlaylistImportResult:
    playlist_ref = playlist.spotify_playlist_url or playlist.spotify_playlist_id
    if playlist_ref is None or not playlist_ref.strip():
        raise ValueError("Playlist has no saved Spotify URL or playlist id.")
    return await _import_spotify_playlist(
        db,
        user_id=user_id,
        playlist_id_or_url=playlist_ref,
        playlist_name_override=playlist.name,
    )
