"""Tests for local download scan (filename fuzzy match) and clear endpoint."""

from __future__ import annotations

from starlette.testclient import TestClient

from track_mapper_api.models.source import SourceTrack
from track_mapper_api.services.local_download_scan import (
    is_audio_display_path,
    parse_artist_title_from_stem,
    score_path_against_source,
    stem_from_display_path,
)


def test_stem_and_parse() -> None:
    assert stem_from_display_path(r"Mixes\Artist - Title.mp3") == "Artist - Title"
    assert parse_artist_title_from_stem("Artist - Title") == ("Artist", "Title")
    assert parse_artist_title_from_stem("OnlyTitle") == (None, "OnlyTitle")


def test_is_audio_display_path() -> None:
    assert is_audio_display_path("a/b/foo.MP3")
    assert not is_audio_display_path("a/readme.txt")


def test_score_path_against_source() -> None:
    st = SourceTrack(
        user_id="u",
        source_kind="x",
        title="Wishlist Row",
        artist="Test Artist",
    )
    sc = score_path_against_source("dl/Test Artist - Wishlist Row.flac", st)
    assert sc >= 99.0


def test_local_scan_and_clear(client: TestClient) -> None:
    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Wishlist Row,Test Artist,ALB,4:00,sp_test_1\n"
    )
    r = client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"import_source": "chosic_csv"},
    )
    assert r.status_code == 200

    scan = client.post(
        "/api/source-tracks/local-scan",
        json={
            "files": [{"path": "Music/Test Artist - Wishlist Row.mp3"}],
            "min_score": 80.0,
        },
    )
    assert scan.status_code == 200
    body = scan.json()
    assert len(body["matched"]) == 1
    assert body["matched"][0]["path"] == "Music/Test Artist - Wishlist Row.mp3"
    assert body["matched"][0]["title"] == "Wishlist Row"
    assert body["matched"][0]["artist"] == "Test Artist"
    assert body["unmatched_files"] == []
    assert body["unmatched_details"] == []
    assert body["min_score"] == 80.0
    assert body["skipped_non_audio"] == 0

    listed = client.get("/api/source-tracks").json()
    assert len(listed) == 1
    assert listed[0]["local_file_path"] == "Music/Test Artist - Wishlist Row.mp3"
    assert listed[0]["manual_dl"] is False
    sid = listed[0]["id"]

    clear = client.delete(f"/api/source-tracks/{sid}/local-file")
    assert clear.status_code == 200
    assert clear.json() == {"cleared": True}

    listed2 = client.get("/api/source-tracks").json()
    assert listed2[0]["local_file_path"] is None
    assert listed2[0]["downloaded_at"] is None
    assert listed2[0]["manual_dl"] is False

    put = client.put(
        f"/api/source-tracks/{sid}/local-file",
        json={"path": "Music/manual/Test Artist - Wishlist Row.mp3"},
    )
    assert put.status_code == 200
    pj = put.json()
    assert pj["path"] == "Music/manual/Test Artist - Wishlist Row.mp3"
    assert pj["title"] == "Wishlist Row"
    assert pj["artist"] == "Test Artist"

    listed3 = client.get("/api/source-tracks").json()
    assert listed3[0]["local_file_path"] == "Music/manual/Test Artist - Wishlist Row.mp3"
    assert listed3[0]["manual_dl"] is False


def test_manual_dl_toggle_and_real_file_clears_it(client: TestClient) -> None:
    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Wishlist Row,Test Artist,ALB,4:00,sp_test_manual\n"
    )
    imported = client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"import_source": "chosic_csv"},
    )
    assert imported.status_code == 200

    listed = client.get("/api/source-tracks").json()
    assert len(listed) == 1
    sid = listed[0]["id"]
    assert listed[0]["manual_dl"] is False

    toggle = client.put(
        f"/api/source-tracks/{sid}/manual-dl",
        json={"manual_dl": True},
    )
    assert toggle.status_code == 200
    assert toggle.json() == {"source_track_id": sid, "manual_dl": True}

    listed2 = client.get("/api/source-tracks").json()
    assert listed2[0]["manual_dl"] is True
    assert listed2[0]["local_file_path"] is None

    put = client.put(
        f"/api/source-tracks/{sid}/local-file",
        json={"path": "Music/manual/Test Artist - Wishlist Row.mp3"},
    )
    assert put.status_code == 200

    listed3 = client.get("/api/source-tracks").json()
    assert listed3[0]["manual_dl"] is False
    assert listed3[0]["local_file_path"] == "Music/manual/Test Artist - Wishlist Row.mp3"

    clear = client.delete(f"/api/source-tracks/{sid}/local-file")
    assert clear.status_code == 200

    listed4 = client.get("/api/source-tracks").json()
    assert listed4[0]["manual_dl"] is False
    assert listed4[0]["local_file_path"] is None


def test_local_scan_match_clears_manual_dl(client: TestClient) -> None:
    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Wishlist Row,Test Artist,ALB,4:00,sp_test_scan_manual\n"
    )
    imported = client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"import_source": "chosic_csv"},
    )
    assert imported.status_code == 200

    listed = client.get("/api/source-tracks").json()
    sid = listed[0]["id"]

    toggle = client.put(
        f"/api/source-tracks/{sid}/manual-dl",
        json={"manual_dl": True},
    )
    assert toggle.status_code == 200

    scan = client.post(
        "/api/source-tracks/local-scan",
        json={
            "files": [{"path": "Music/Test Artist - Wishlist Row.mp3"}],
            "min_score": 80.0,
        },
    )
    assert scan.status_code == 200

    listed2 = client.get("/api/source-tracks").json()
    assert listed2[0]["manual_dl"] is False
    assert listed2[0]["local_file_path"] == "Music/Test Artist - Wishlist Row.mp3"


def test_local_scan_unmatched_best_overall_when_correct_row_already_has_file(
    client: TestClient,
) -> None:
    """Auto-match only considers sources with no local path; UI still shows true best source."""
    client.post(
        "/api/playlists/import",
        files={
            "file": (
                "teed.csv",
                (
                    "Song,Artist,Album,Duration,Spotify Track Id\n"
                    "A Dream I Have,TEED,ALB,4:33,sp_teed_1\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        data={"import_source": "chosic_csv"},
    )
    client.post(
        "/api/playlists/import",
        files={
            "file": (
                "yuk.csv",
                (
                    "Song,Artist,Album,Duration,Spotify Track Id\n"
                    "I Don't Have A Drum Machine,Yuksek,ALB,4:00,sp_yuk_1\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        data={"import_source": "chosic_csv"},
    )
    src = client.get("/api/source-tracks").json()
    assert len(src) == 2
    teed = next(s for s in src if s["artist"] == "TEED")
    r_put = client.put(
        f"/api/source-tracks/{teed['id']}/local-file",
        json={"path": "old/wrong.mp3"},
    )
    assert r_put.status_code == 200

    scan = client.post(
        "/api/source-tracks/local-scan",
        json={
            "files": [{"path": "new tracks/TEED - A Dream I Have.mp3"}],
            "min_score": 80.0,
        },
    )
    assert scan.status_code == 200
    body = scan.json()
    assert body["unmatched_files"] == ["new tracks/TEED - A Dream I Have.mp3"]
    assert len(body["unmatched_details"]) == 1
    det = body["unmatched_details"][0]
    assert det["best_source_artist"] == "TEED"
    assert det["best_source_title"] == "A Dream I Have"
    assert det["best_score"] >= 95.0
    assert det["best_source_already_has_file"] is True
    assert det["below_threshold"] is True


def test_local_scan_skips_non_audio(client: TestClient) -> None:
    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Wishlist Row,Test Artist,ALB,4:00,sp_test_2\n"
    )
    client.post(
        "/api/playlists/import",
        files={"file": ("pl2.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"import_source": "chosic_csv"},
    )
    scan = client.post(
        "/api/source-tracks/local-scan",
        json={
            "files": [{"path": "notes.txt"}, {"path": "a/Test Artist - Wishlist Row.mp3"}],
        },
    )
    assert scan.status_code == 200
    b = scan.json()
    assert b["skipped_non_audio"] == 1
    assert len(b["matched"]) == 1
    assert b["min_score"] == 80.0
    assert b["unmatched_details"] == []
