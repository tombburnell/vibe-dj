"""API smoke tests (SQLite in-memory via conftest)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
        files={"file": ("my_unit_pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"import_source": "chosic_csv"},
    )
    assert r.status_code == 200
    assert r.json()["rows_linked"] == 1

    src = client.get("/api/source-tracks").json()
    assert len(src) == 1
    assert src[0]["playlist_names"] == ["my_unit_pl"]
    assert src[0]["top_match_title"] is None
    assert src[0]["top_match_score"] is None
    sid = src[0]["id"]

    batch = client.post(
        "/api/source-tracks/top-matches",
        json={"source_track_ids": [sid]},
    )
    assert batch.status_code == 200
    bj = batch.json()
    assert len(bj) == 1
    assert bj[0]["source_track_id"] == sid
    assert bj[0]["top_match_title"] is None

    cand = client.get(f"/api/source-tracks/{sid}/candidates").json()
    assert isinstance(cand, list)

    match = client.post("/api/match/run", json={})
    assert match.status_code == 200
    mj = match.json()
    assert mj["library_snapshot_id"] is None
    assert mj["matched_count"] == 0

    pls = client.get("/api/playlists")
    assert pls.status_code == 200
    pl_list = pls.json()
    assert len(pl_list) == 1
    assert pl_list[0]["name"] == "my_unit_pl"
    pid = pl_list[0]["id"]

    del_r = client.delete(f"/api/playlists/{pid}")
    assert del_r.status_code == 204

    assert client.get("/api/playlists").json() == []
    src_after = client.get("/api/source-tracks").json()
    assert len(src_after) == 1
    assert src_after[0]["playlist_names"] == []


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
        files={"file": ("koko_groove.csv", csv_body.encode("utf-8"), "text/csv")},
        data={},
    ).status_code == 200

    listed_src = client.get("/api/source-tracks").json()
    assert len(listed_src) == 1
    assert listed_src[0]["playlist_names"] == ["koko_groove"]
    # List GET embeds best-match overlay (same rules as POST /top-matches).
    assert listed_src[0]["top_match_title"] == "Test Song One"
    assert listed_src[0]["top_match_is_picked"] is False
    assert listed_src[0]["is_rejected_no_match"] is False
    sid = listed_src[0]["id"]
    batch = client.post(
        "/api/source-tracks/top-matches",
        json={"source_track_ids": [sid]},
    ).json()
    assert len(batch) == 1
    assert batch[0]["top_match_title"] == "Test Song One"
    assert batch[0]["top_match_artist"] == "Test Act"
    assert batch[0]["top_match_score"] is not None
    assert batch[0]["top_match_score"] > 0.5
    assert batch[0]["top_match_is_picked"] is False
    assert batch[0]["is_rejected_no_match"] is False
    assert batch[0]["top_match_library_track_id"] is not None
    assert batch[0]["top_match_below_minimum"] is False

    match = client.post("/api/match/run", json={}).json()
    assert match["library_snapshot_id"] is not None
    assert match["skipped_count"] >= 0
    assert match["matched_count"] >= 0


def test_wishlist_batch_ignore_and_restore(client: TestClient) -> None:
    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Wishlist Row,Test Artist,ALB,4:00,sp_wl_ignore_1\n"
    )
    assert client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={"import_source": "chosic_csv"},
    ).status_code == 200
    src = client.get("/api/source-tracks").json()
    assert len(src) == 1
    sid = src[0]["id"]
    assert src[0]["on_wishlist"] is True

    r = client.post(
        "/api/source-tracks/wishlist-batch",
        json={"source_track_ids": [sid], "on_wishlist": False},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "updated_count": 1}

    src2 = client.get("/api/source-tracks").json()
    assert len(src2) == 1
    assert src2[0]["on_wishlist"] is False

    assert (
        client.post(
            "/api/source-tracks/wishlist-batch",
            json={"source_track_ids": [sid], "on_wishlist": True},
        ).status_code
        == 200
    )
    src3 = client.get("/api/source-tracks").json()
    assert src3[0]["on_wishlist"] is True


def test_match_reject_batch(client: TestClient) -> None:
    tsv_path = _FIXTURES / "minimal_rekordbox.tsv"
    assert client.post(
        "/api/library-snapshots/import",
        files={"file": ("m.tsv", tsv_path.read_bytes(), "text/tab-separated-values")},
    ).status_code == 200

    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Test Song One,Test Act,ALB,4:30,sp_batch_rej_1\n"
    )
    assert client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={},
    ).status_code == 200

    src = client.get("/api/source-tracks").json()
    assert len(src) == 1
    sid = src[0]["id"]

    assert client.post("/api/match/run", json={}).status_code == 200

    r = client.post("/api/match/reject/batch", json={"source_track_ids": [sid, sid]})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "rejected_count": 1}

    top = client.post(
        "/api/source-tracks/top-matches",
        json={"source_track_ids": [sid]},
    ).json()
    assert len(top) == 1
    assert top[0]["is_rejected_no_match"] is True


def test_find_amazon_links_no_snapshot(client: TestClient) -> None:
    r = client.post("/api/source-tracks/find-amazon-links", json={})
    assert r.status_code == 200
    j = r.json()
    assert j["searched_count"] == 0
    assert j["skipped_not_need_count"] == 0
    assert j["skipped_cached_count"] == 0
    assert j["error_count"] == 0


def test_find_amazon_links_need_queue_mocked(client: TestClient) -> None:
    tsv_path = _FIXTURES / "minimal_rekordbox.tsv"
    assert client.post(
        "/api/library-snapshots/import",
        files={"file": ("m.tsv", tsv_path.read_bytes(), "text/tab-separated-values")},
    ).status_code == 200

    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Other Song,Other Act,ALB,4:30,sp_other_1\n"
    )
    assert client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={},
    ).status_code == 200

    src = client.get("/api/source-tracks").json()
    assert len(src) == 1
    sid = src[0]["id"]

    assert client.post("/api/match/reject", json={"source_track_id": sid}).status_code == 200

    from track_mapper_api.services.web_search_service import WebSearchHit

    fake_query = '(site:tidal.com OR site:amazon.com) "Other Song"'
    fake_hits = [
        WebSearchHit(
            url="https://music.amazon.com/tracks/abc",
            title="T1",
            body="",
            matched_domain="amazon.com",
            match_score=90.0,
        ),
        WebSearchHit(
            url="https://music.amazon.com/albums/xyz",
            title="T2",
            body="",
            matched_domain="amazon.com",
            match_score=80.0,
        ),
    ]

    with patch("track_mapper_api.services.find_amazon_links.MultiSiteWebSearcher") as MS:
        inst = MS.return_value
        inst.search = MagicMock(return_value=(fake_query, fake_hits))
        r = client.post(
            "/api/source-tracks/find-amazon-links",
            json={"source_track_ids": [sid], "force": False},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["searched_count"] == 1
    assert body["skipped_not_need_count"] == 0

    src2 = client.get("/api/source-tracks").json()
    row = src2[0]
    assert row["amazon_url"] == "https://music.amazon.com/tracks/abc"
    assert row["amazon_price"] is None
    assert row["amazon_link_title"] == "T1"
    assert row["amazon_link_match_score"] == 90.0
    assert row["amazon_last_searched_at"] is not None
    assert len(row["amazon_candidates"]) == 2
    assert row["amazon_candidates"][0]["url"] == "https://music.amazon.com/tracks/abc"
    assert row["amazon_candidates"][0]["match_score"] == 90.0
    assert row["amazon_candidates"][0]["broken"] is False
    assert row["amazon_candidates"][1]["url"] == "https://music.amazon.com/albums/xyz"
    assert row["amazon_candidates"][1]["match_score"] == 80.0
    assert row["amazon_candidates"][1]["artist"] is None

    with patch("track_mapper_api.services.find_amazon_links.MultiSiteWebSearcher") as MS:
        inst = MS.return_value
        inst.search = MagicMock(return_value=(fake_query, fake_hits))
        r2 = client.post(
            "/api/source-tracks/find-amazon-links",
            json={"source_track_ids": [sid], "force": False},
        )
    assert r2.json()["searched_count"] == 0
    assert r2.json()["skipped_cached_count"] == 1


def test_mark_amazon_link_broken_alternate_then_primary(client: TestClient) -> None:
    tsv_path = _FIXTURES / "minimal_rekordbox.tsv"
    assert client.post(
        "/api/library-snapshots/import",
        files={"file": ("m.tsv", tsv_path.read_bytes(), "text/tab-separated-values")},
    ).status_code == 200

    csv_body = (
        "Song,Artist,Album,Duration,Spotify Track Id\n"
        "Other Song,Other Act,ALB,4:30,sp_other_1\n"
    )
    assert client.post(
        "/api/playlists/import",
        files={"file": ("pl.csv", csv_body.encode("utf-8"), "text/csv")},
        data={},
    ).status_code == 200

    src = client.get("/api/source-tracks").json()
    sid = src[0]["id"]
    assert client.post("/api/match/reject", json={"source_track_id": sid}).status_code == 200

    from track_mapper_api.services.web_search_service import WebSearchHit

    fake_query = '(site:tidal.com OR site:amazon.com) "Other Song"'
    fake_hits = [
        WebSearchHit(
            url="https://music.amazon.com/tracks/abc",
            title="T1",
            body="",
            matched_domain="amazon.com",
            match_score=90.0,
        ),
        WebSearchHit(
            url="https://music.amazon.com/albums/xyz",
            title="T2",
            body="",
            matched_domain="amazon.com",
            match_score=80.0,
        ),
    ]

    with patch("track_mapper_api.services.find_amazon_links.MultiSiteWebSearcher") as MS:
        inst = MS.return_value
        inst.search = MagicMock(return_value=(fake_query, fake_hits))
        assert client.post(
            "/api/source-tracks/find-amazon-links",
            json={"source_track_ids": [sid], "force": False},
        ).status_code == 200

    alt = client.post(
        f"/api/source-tracks/{sid}/mark-link-broken",
        json={"url": "https://music.amazon.com/albums/xyz"},
    )
    assert alt.status_code == 200
    u1 = alt.json()
    assert u1["amazon_url"] == "https://music.amazon.com/tracks/abc"
    by_url = {c["url"]: c for c in u1["amazon_candidates"]}
    assert by_url["https://music.amazon.com/albums/xyz"]["broken"] is True
    assert by_url["https://music.amazon.com/tracks/abc"]["broken"] is False

    prime = client.post(
        f"/api/source-tracks/{sid}/mark-link-broken",
        json={"url": "https://music.amazon.com/tracks/abc"},
    )
    assert prime.status_code == 200
    u2 = prime.json()
    assert u2["amazon_url"] is None
    assert all(c.get("broken") for c in u2["amazon_candidates"])

    missing = client.post(
        f"/api/source-tracks/{sid}/mark-link-broken",
        json={"url": "https://not-in-list.example/foo"},
    )
    assert missing.status_code == 404
