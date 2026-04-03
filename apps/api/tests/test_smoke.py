"""Smoke tests for dummy list endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from track_mapper_api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_library_tracks_dummy() -> None:
    r = client.get("/api/library-tracks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]["title"] == "Untold"
    assert "file_path" in data[0]


def test_source_tracks_dummy() -> None:
    r = client.get("/api/source-tracks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 4
    assert data[0]["playlist_names"] == ["Koko Groove", "Peak Time"]
