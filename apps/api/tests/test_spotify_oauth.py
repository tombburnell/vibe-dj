"""Spotify OAuth API (status + token exchange mocked)."""

from __future__ import annotations

from unittest.mock import patch

from starlette.testclient import TestClient


def test_spotify_oauth_config(client: TestClient) -> None:
    with (
        patch(
            "track_mapper_api.routers.spotify_oauth.get_spotify_client_id_public",
            return_value="testclientid",
        ),
        patch(
            "track_mapper_api.routers.spotify_oauth.get_spotify_redirect_uri",
            return_value="http://127.0.0.1:5173/spotify-callback",
        ),
    ):
        r = client.get("/api/integrations/spotify/oauth/config")
    assert r.status_code == 200
    j = r.json()
    assert j["client_id"] == "testclientid"
    assert "5173" in j["redirect_uri"]


def test_spotify_oauth_status_disconnected(client: TestClient) -> None:
    r = client.get("/api/integrations/spotify/oauth/status")
    assert r.status_code == 200
    assert r.json() == {"connected": False, "spotify_user_id": None}


def test_spotify_oauth_token_mocked(client: TestClient) -> None:
    fake_tokens = {
        "access_token": "acc",
        "refresh_token": "ref",
        "expires_in": 3600,
        "scope": "playlist-read-private playlist-read-collaborative",
    }
    with (
        patch(
            "track_mapper_api.routers.spotify_oauth.exchange_authorization_code",
            return_value=fake_tokens,
        ),
        patch(
            "track_mapper_api.routers.spotify_oauth.fetch_spotify_profile_id",
            return_value="spotify-user-xyz",
        ),
    ):
        r = client.post(
            "/api/integrations/spotify/oauth/token",
            json={
                "code": "auth-code",
                "code_verifier": "a" * 43,
                "redirect_uri": "http://127.0.0.1:5173/spotify-callback",
            },
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    st = client.get("/api/integrations/spotify/oauth/status")
    assert st.json()["connected"] is True
    assert st.json()["spotify_user_id"] == "spotify-user-xyz"

    disc = client.delete("/api/integrations/spotify/oauth/disconnect")
    assert disc.status_code == 204
    assert client.get("/api/integrations/spotify/oauth/status").json()["connected"] is False


def test_spotify_oauth_token_redirect_mismatch(client: TestClient) -> None:
    r = client.post(
        "/api/integrations/spotify/oauth/token",
        json={
            "code": "x",
            "code_verifier": "b" * 43,
            "redirect_uri": "http://evil.example/cb",
        },
    )
    assert r.status_code == 400
