"""API smoke tests (SQLite in-memory via conftest)."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_library_tracks_empty(client: TestClient) -> None:
    r = client.get("/api/library-tracks")
    assert r.status_code == 200
    assert r.json() == {"items": [], "next_cursor": None}


def test_source_tracks_empty(client: TestClient) -> None:
    r = client.get("/api/source-tracks")
    assert r.status_code == 200
    assert r.json() == []


def test_import_library_and_list(client: TestClient) -> None:
    tsv_path = _FIXTURES / "minimal_rekordbox.tsv"
    r = client.post(
        "/api/library-snapshots/import",
        files={"file": ("minimal.tsv", tsv_path.read_bytes(), "text/tab-separated-values")},
        data={"label": "test snap"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["track_count"] == 2
    assert "snapshot_id" in body

    listed = client.get("/api/library-tracks").json()
    assert len(listed["items"]) == 2
    titles = {listed["items"][0]["title"], listed["items"][1]["title"]}
    assert titles == {"Test Song One", "Test Song Two"}


def test_import_playlist_and_candidates_shape(client: TestClient) -> None:
    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Wishlist Row,Test Artist,ALB,4:00,sp_test_1\n"
    )
    r = client.post(
        "/api/playlists/import",
        files={"file": ("p.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"playlist_name": "Unit PL", "import_source": "chosic_csv"},
    )
    assert r.status_code == 200
    assert r.json()["rows_linked"] == 1

    src = client.get("/api/source-tracks").json()
    assert len(src) == 1
    sid = src[0]["id"]

    cand = client.get(f"/api/source-tracks/{sid}/candidates").json()
    assert isinstance(cand, list)

    match = client.post("/api/match/run", json={})
    assert match.status_code == 200
    mj = match.json()
    assert mj["library_snapshot_id"] is None
    assert mj["matched_count"] == 0


def test_match_run_with_library_and_sources(client: TestClient) -> None:
    tsv_path = _FIXTURES / "minimal_rekordbox.tsv"
    assert client.post(
        "/api/library-snapshots/import",
        files={"file": ("m.tsv", tsv_path.read_bytes(), "text/tab-separated-values")},
    ).status_code == 200

    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Test Song One,Test Act,ALB,4:30,sp_full_1\n"
    )
    assert client.post(
        "/api/playlists/import",
        files={"file": ("p.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"playlist_name": "PL"},
    ).status_code == 200

    match = client.post("/api/match/run", json={}).json()
    assert match["library_snapshot_id"] is not None
    assert match["skipped_count"] >= 0
    assert match["matched_count"] >= 0
