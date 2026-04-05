"""Spotify public playlist import (parsed ids + mocked Web API)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from track_mapper_api.services.spotify_web_api import (
    SpotifyPlaylistBundle,
    SpotifyPlaylistParseError,
    SpotifyTrackRow,
    parse_spotify_playlist_id,
)


@pytest.mark.parametrize(
    ("raw", "expected_id"),
    [
        ("37i9dQZF1DXcBWIGoYBM5M", "37i9dQZF1DXcBWIGoYBM5M"),
        (
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
            "37i9dQZF1DXcBWIGoYBM5M",
        ),
        (
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc",
            "37i9dQZF1DXcBWIGoYBM5M",
        ),
        (
            "https://open.spotify.com/intl-de/playlist/37i9dQZF1DXcBWIGoYBM5M",
            "37i9dQZF1DXcBWIGoYBM5M",
        ),
        ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "37i9dQZF1DXcBWIGoYBM5M"),
    ],
)
def test_parse_spotify_playlist_id_ok(raw: str, expected_id: str) -> None:
    assert parse_spotify_playlist_id(raw) == expected_id


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "not-a-url",
        "https://open.spotify.com/track/37i9dQZF1DXcBWIGoYBM5M",
        "https://open.spotify.com/playlist/short",
    ],
)
def test_parse_spotify_playlist_id_rejects(bad: str) -> None:
    with pytest.raises(SpotifyPlaylistParseError):
        parse_spotify_playlist_id(bad)


def test_import_spotify_playlist_mocked(client: TestClient) -> None:
    bundle = SpotifyPlaylistBundle(
        playlist_name="API Mix",
        tracks=[
            SpotifyTrackRow(
                spotify_id="tr1",
                title="One",
                artist="Artist A",
                album="Alb",
                duration_ms=180000,
            ),
        ],
    )
    with (
        patch(
            "track_mapper_api.services.spotify_playlist_import.get_spotify_user_access_token",
            new_callable=AsyncMock,
            return_value="user-access-token",
        ),
        patch(
            "track_mapper_api.services.spotify_playlist_import.fetch_playlist_tracks",
            return_value=bundle,
        ),
    ):
        r = client.post(
            "/api/playlists/import-spotify",
            json={"playlist_id_or_url": "37i9dQZF1DXcBWIGoYBM5M"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_linked"] == 1
    assert body["new_source_tracks"] == 1

    src = client.get("/api/source-tracks").json()
    assert len(src) == 1
    assert src[0]["title"] == "One"
    assert src[0]["spotify_id"] == "tr1"
    assert src[0]["source_kind"] == "spotify_web_api"

    pls = client.get("/api/playlists").json()
    assert len(pls) == 1
    assert pls[0]["name"] == "API Mix"
    assert pls[0]["import_source"] == "spotify_web_api"


def test_import_spotify_playlist_twice_reuses_one_playlist(client: TestClient) -> None:
    bundle = SpotifyPlaylistBundle(
        playlist_name="API Mix",
        tracks=[
            SpotifyTrackRow(
                spotify_id="tr1",
                title="One",
                artist="Artist A",
                album="Alb",
                duration_ms=180000,
            ),
        ],
    )
    with (
        patch(
            "track_mapper_api.services.spotify_playlist_import.get_spotify_user_access_token",
            new_callable=AsyncMock,
            return_value="user-access-token",
        ),
        patch(
            "track_mapper_api.services.spotify_playlist_import.fetch_playlist_tracks",
            return_value=bundle,
        ),
    ):
        r1 = client.post(
            "/api/playlists/import-spotify",
            json={"playlist_id_or_url": "37i9dQZF1DXcBWIGoYBM5M"},
        )
        r2 = client.post(
            "/api/playlists/import-spotify",
            json={"playlist_id_or_url": "37i9dQZF1DXcBWIGoYBM5M"},
        )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["playlist_id"] == r2.json()["playlist_id"]
    assert r2.json()["rows_linked"] == 0
    assert r2.json()["new_source_tracks"] == 0
    pls = client.get("/api/playlists").json()
    assert len(pls) == 1


def test_import_spotify_not_connected(client: TestClient) -> None:
    with patch(
        "track_mapper_api.services.spotify_playlist_import.get_spotify_user_access_token",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = client.post(
            "/api/playlists/import-spotify",
            json={"playlist_id_or_url": "37i9dQZF1DXcBWIGoYBM5M"},
        )
    assert r.status_code == 401


def test_import_spotify_bad_input(client: TestClient) -> None:
    r = client.post(
        "/api/playlists/import-spotify",
        json={"playlist_id_or_url": "https://example.com/"},
    )
    assert r.status_code == 400
