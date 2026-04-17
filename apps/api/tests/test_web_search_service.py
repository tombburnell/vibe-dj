"""Tests for multi-site web search (web_search_service)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from track_mapper_api.services import web_search_service as wss
from track_mapper_api.services.link_match_scoring import (
    match_query_for_track,
    score_artist_title_against_query,
    score_web_hit_snippet,
)
from track_mapper_api.routers import source_tracks as source_tracks_router
from track_mapper_api.services.web_search_service import (
    MultiSiteWebSearcher,
    SiteSearchRule,
    WebSearchHit,
    _canonical_url_key,
    build_multisite_ddg_query,
    default_site_rules,
    display_link_title,
    multisite_repeat_search_url,
)

_TIDAL_TEST_RULE = SiteSearchRule(
    domain="tidal.com",
    url_exclude_patterns=(r"/browse/artist/",),
    url_transforms=((r"/browse/album/", "/album/"),),
    title_transforms=((r"\s+on\s+TIDAL\s*$", ""),),
)


def test_amazon_candidates_from_db_drops_domain_used_as_artist() -> None:
    raw = [
        {
            "url": "https://soundcloud.com/u/track",
            "title": "Stream Nice To Each Other by Olivia Dean — soundcloud.com",
            "artist": "soundcloud.com",
            "match_score": 26.0,
        }
    ]
    out = source_tracks_router._amazon_candidates_from_db(raw)
    assert len(out) == 1
    assert out[0].artist is None
    assert out[0].title == "Nice To Each Other by Olivia Dean"


def test_amazon_candidates_from_db_prepends_primary_when_missing_from_json() -> None:
    """Legacy rows stored only alternates in JSON; ``amazon_url`` pointed at the best hit."""
    raw = [
        {
            "url": "https://music.amazon.com/albums/xyz",
            "title": "Alt",
            "match_score": 80.0,
        }
    ]
    st = SimpleNamespace(
        amazon_url="https://music.amazon.com/tracks/abc",
        amazon_link_title="Best T",
        amazon_link_match_score=90.0,
        amazon_price=None,
    )
    out = source_tracks_router._amazon_candidates_from_db(raw, st=st)
    assert len(out) == 2
    assert out[0].url == "https://music.amazon.com/tracks/abc"
    assert out[0].match_score == 90.0
    assert out[1].url == "https://music.amazon.com/albums/xyz"


def test_amazon_candidates_from_db_no_duplicate_when_primary_in_json() -> None:
    raw = [
        {
            "url": "https://music.amazon.com/tracks/abc",
            "title": "Same",
            "match_score": 90.0,
        }
    ]
    st = SimpleNamespace(
        amazon_url="https://music.amazon.com/tracks/abc",
        amazon_link_title="Same",
        amazon_link_match_score=90.0,
        amazon_price=None,
    )
    out = source_tracks_router._amazon_candidates_from_db(raw, st=st)
    assert len(out) == 1


def test_display_link_title_matches_ingest_rules() -> None:
    assert (
        display_link_title(
            "https://music.amazon.com/tracks/x",
            "Baby D - Let Me Be Your Fantasy - Amazon.com Music",
        )
        == "Baby D - Let Me Be Your Fantasy"
    )
    assert (
        display_link_title(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "My Song - YouTube",
        )
        == "My Song"
    )
    raw = (
        "Stream X by Y | Listen online for free — soundcloud.com"
    )
    assert "| Listen" not in (display_link_title("https://soundcloud.com/a/b", raw) or "")


def test_display_link_title_strips_amazon_com_prefix_and_em_dash_domain() -> None:
    assert (
        display_link_title(
            "https://www.amazon.com/dp/X",
            "Amazon.com: Blondie Mix.",
        )
        == "Blondie Mix."
    )
    assert (
        display_link_title(
            "https://music.amazon.com/albums/y",
            "Blondie - Remixed Remade Remodeled — amazon.com",
        )
        == "Blondie - Remixed Remade Remodeled"
    )


def test_display_link_title_strips_amazon_unlimited_play_and_song_by() -> None:
    base = "https://music.amazon.com/albums/B0FQWYKQDV"
    assert (
        display_link_title(
            base,
            "Play I Like It Like That by Fcukers on Amazon Music Unlimited",
        )
        == "I Like It Like That by Fcukers"
    )
    assert (
        display_link_title(
            base,
            "Play I Like It Like That by Chris Kenner on Amazon Music Unlimited — Fcukers",
        )
        == "I Like It Like That by Chris Kenner"
    )
    assert (
        display_link_title(
            "https://music.amazon.com/tracks/B0FQXL4BYK",
            "I Like It Like That [Explicit] song by Fcukers from I Like It Like That — Fcukers",
        )
        == "I Like It Like That [Explicit]"
    )
    assert (
        display_link_title(
            "https://music.amazon.com/albums/B0DZT44CW9",
            "I Like It Like That (2019 — Remaster) - music.amazon.com",
        )
        == "I Like It Like That (2019 — Remaster)"
    )


def test_display_link_title_strips_soundcloud_listen_to_songs_pipe() -> None:
    raw = (
        "Stream DJ Blondie music | Listen to songs, albums, playlists for free — soundcloud.com"
    )
    out = display_link_title("https://soundcloud.com/blondie", raw)
    assert out == "DJ Blondie music"
    assert "| Listen" not in (out or "")


def test_display_link_title_amazon_regional_host_and_digital_music_suffix() -> None:
    assert (
        display_link_title(
            "https://www.amazon.co.uk/dp/B000123",
            "Like It Like That (2019 — Remaster) - music.amazon.com",
        )
        == "Like It Like That (2019 — Remaster)"
    )
    assert (
        display_link_title(
            "https://www.amazon.com/dp/X",
            "You Don't Know Me (feat. Duane Harden) : Armand Van Helden: Digital Music",
        )
        == "You Don't Know Me (feat. Duane Harden) : Armand Van Helden"
    )


def test_display_link_title_strips_soundcloud_stream_prefix_and_brand_suffix() -> None:
    raw = "Stream Daphni - Clavicle (Unreleased) by Komoso - SoundCloud"
    assert (
        display_link_title("https://soundcloud.com/komoso/clavicle", raw)
        == "Daphni - Clavicle (Unreleased) by Komoso"
    )


def test_display_link_title_strips_domain_suffix_hyphen_and_amazon_music_clause() -> None:
    assert (
        display_link_title(
            "https://soundcloud.com/niminomusic/shaking-things-up",
            "Stream Shaking Things Up by nimino - soundcloud.com",
        )
        == "Shaking Things Up by nimino"
    )
    assert (
        display_link_title(
            "https://www.amazon.com/Better-Manta/dp/B0FN4WYSPG",
            "Better by nimino & Manta on Amazon Music — amazon.com",
        )
        == "Better by nimino & Manta"
    )
    assert display_link_title("https://www.amazon.com/x", "Glow — amazon.com") == "Glow"


def test_link_match_scoring_snippet_vs_quoted_track() -> None:
    mq = match_query_for_track("nimino", "Shaking Things Up")
    hit = WebSearchHit(
        url="https://tidal.com/album/1",
        title="Shaking Things Up by nimino on TIDAL",
        body="",
        matched_domain="tidal.com",
    )
    assert score_web_hit_snippet(hit, mq) > 40.0


def test_link_match_scoring_artist_title_order_invariant() -> None:
    q = match_query_for_track("A", "T")
    a = score_artist_title_against_query("Artist", "Title", q)
    b = score_artist_title_against_query("Title", "Artist", q)
    assert a == b


def test_multisite_repeat_search_url_brave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("track_mapper_api.config.USE_SERPER", False)
    monkeypatch.setattr("track_mapper_api.config.SERPER_API_KEY", "")
    monkeypatch.setattr(wss, "DDGS_TEXT_BACKEND", "brave")
    u = multisite_repeat_search_url("a b")
    assert "search.brave.com" in u
    assert "a%20b" in u or "a+b" in u


def test_multisite_repeat_search_url_google_when_serper_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("track_mapper_api.config.USE_SERPER", True)
    monkeypatch.setattr("track_mapper_api.config.SERPER_API_KEY", "secret")
    u = multisite_repeat_search_url("a b")
    assert "google.com/search" in u
    assert "a%20b" in u or "a+b" in u


def test_multisite_repeat_search_url_forced_providers_ignore_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("track_mapper_api.config.USE_SERPER", False)
    monkeypatch.setattr("track_mapper_api.config.SERPER_API_KEY", "")
    monkeypatch.setattr(wss, "DDGS_TEXT_BACKEND", "brave")
    assert "google.com/search" in multisite_repeat_search_url("q", web_search_provider="serper")
    assert "search.brave.com" in multisite_repeat_search_url("q", web_search_provider="ddg")


def test_multi_site_search_override_ddg_uses_ddgs_not_serper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("track_mapper_api.config.USE_SERPER", True)
    monkeypatch.setattr("track_mapper_api.config.SERPER_API_KEY", "k")

    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://soundcloud.com/a/first", "title": "sc", "body": ""},
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    called: list[str] = []

    def no_serper(**kwargs: object) -> list[dict[str, str]]:
        called.append("serper")
        return []

    monkeypatch.setattr(wss, "serper_search", no_serper)
    _q, hits = MultiSiteWebSearcher().search(
        artist="x",
        track="y",
        max_results=10,
        web_search_provider="ddg",
    )
    assert not called
    assert len(hits) == 1


def test_multi_site_search_serper_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("track_mapper_api.config.USE_SERPER", True)
    monkeypatch.setattr("track_mapper_api.config.SERPER_API_KEY", "k")

    def fake_serper(*, query: str, max_results: int, api_key: str) -> list[dict[str, str]]:
        assert api_key == "k"
        assert "x" in query and "y" in query and "amazon track" in query
        return [
            {"href": "https://soundcloud.com/a/first", "title": "sc", "body": "snippet"},
        ]

    monkeypatch.setattr(wss, "serper_search", fake_serper)
    _q, hits = MultiSiteWebSearcher().search(artist="x", track="y", max_results=10)
    assert len(hits) == 1
    assert hits[0].url == "https://soundcloud.com/a/first"
    assert hits[0].body == "snippet"


def test_build_multisite_ddg_query_shape() -> None:
    sites = default_site_rules()
    q = build_multisite_ddg_query(artist="nimino", track="Shaking Things Up", sites=sites)
    assert "nimino" in q
    assert "Shaking Things Up" in q
    assert q.strip() == "nimino Shaking Things Up"


def test_default_site_order() -> None:
    domains = [r.domain for r in default_site_rules()]
    assert domains == [
        "amazon.com",
        "soundcloud.com",
        "bandcamp.com",
        "youtube.com",
        "youtu.be",
        "beatport.com",
    ]


def test_youtube_shorts_urls_excluded_from_site_rules() -> None:
    yt = next(r for r in default_site_rules() if r.domain == "youtube.com")
    compiled = yt.compiled_excludes()
    assert wss._url_excluded_by_url_patterns(
        "https://www.youtube.com/shorts/heyvuCiiPkw", compiled
    )
    assert not wss._url_excluded_by_url_patterns(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", compiled
    )


def test_multi_site_search_sorts_by_domain_then_ddg_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Site order from ``default_site_rules``; within a domain, DDG row order kept."""

    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://soundcloud.com/a/first", "title": "sc", "body": ""},
                {
                    "href": "https://www.youtube.com/watch?v=abcdefghijk",
                    "title": "yt",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="x", track="y", max_results=10)
    assert len(hits) == 2
    assert {h.matched_domain for h in hits} == {"soundcloud.com", "youtube.com"}


def test_multi_site_search_preserves_ddg_order_within_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Within the same domain, ties break by backend row order (after per-domain cap)."""

    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://listen.tidal.com/browse/artist/1", "title": "skip", "body": ""},
                {"href": "https://soundcloud.com/a/first", "title": "1", "body": ""},
                {"href": "https://music.amazon.com/artists/B0A", "title": "skip", "body": ""},
                {"href": "https://soundcloud.com/b/second", "title": "2", "body": ""},
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="x", track="y", max_results=10)
    assert [h.url for h in hits] == [
        "https://soundcloud.com/a/first",
        "https://soundcloud.com/b/second",
    ]


def test_multi_site_search_filters_amazon_album(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://music.amazon.com/albums/B0ALBUM",
                    "title": "Album page",
                    "body": "",
                },
                {
                    "href": "https://music.amazon.com/artists/B0ART",
                    "title": "Artist page",
                    "body": "",
                },
                {
                    "href": "https://music.amazon.com/tracks/B0TRACK",
                    "title": "Track page",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    searcher = MultiSiteWebSearcher()
    _q, hits = searcher.search(artist="a", track="t", max_results=10)
    assert len(hits) == 2
    assert hits[0].url.endswith("/tracks/B0TRACK")
    assert hits[1].url.endswith("/albums/B0ALBUM")
    assert hits[0].matched_domain == "amazon.com"
    assert hits[1].matched_domain == "amazon.com"


def test_multi_site_search_filters_tidal_browse_artist(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://listen.tidal.com/browse/artist/7785739",
                    "title": "Artist",
                    "body": "",
                },
                {
                    "href": "https://listen.tidal.com/browse/track/12345",
                    "title": "Track",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher(sites=(_TIDAL_TEST_RULE,)).search(
        artist="a", track="b", max_results=10
    )
    assert len(hits) == 1
    assert "/browse/track/" in hits[0].url


def test_multi_site_search_skips_unknown_host(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://example.com/x", "title": "x", "body": ""},
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    q, hits = MultiSiteWebSearcher().search(artist="a", track="b", max_results=10)
    assert hits == []


def test_soundcloud_single_segment_profile_url_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://m.soundcloud.com/niminomusic",
                    "title": "profile",
                    "body": "",
                },
                {
                    "href": "https://soundcloud.com/niminomusic/shaking-things-up",
                    "title": "track",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="a", track="b", max_results=10)
    assert len(hits) == 1
    assert "shaking-things-up" in hits[0].url
    assert hits[0].matched_domain == "soundcloud.com"


def test_soundcloud_sets_path_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://soundcloud.com/u/sets/mix-1", "title": "pl", "body": ""},
                {"href": "https://soundcloud.com/u/track-1", "title": "tr", "body": ""},
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="a", track="b", max_results=10)
    assert len(hits) == 1
    assert "/sets/" not in hits[0].url


def test_max_two_hits_per_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://soundcloud.com/a/one", "title": "x", "body": ""},
                {"href": "https://soundcloud.com/b/two", "title": "x", "body": ""},
                {"href": "https://soundcloud.com/c/three", "title": "x", "body": ""},
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="a", track="b", max_results=10)
    assert len(hits) == 2
    assert all("soundcloud.com" in h.url for h in hits)


def test_title_transform_strips_amazon_com_music_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://music.amazon.com/tracks/x",
                    "title": "Baby D - Let Me Be Your Fantasy - Amazon.com Music",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="a", track="b", max_results=10)
    assert hits[0].title == "Baby D - Let Me Be Your Fantasy"


def test_title_transform_strips_soundcloud_listen_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://soundcloud.com/levela/bootleg",
                    "title": (
                        "Stream Baby D - Let Me Be Your Fantasy (LEVELA BOOTLEG) **Free Download** "
                        "by LEVELA | Listen online for free — soundcloud.com"
                    ),
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher().search(artist="a", track="b", max_results=10)
    assert "| Listen" not in hits[0].title
    assert "soundcloud.com" not in hits[0].title.lower()


def test_title_transform_strips_tidal_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://tidal.com/browse/track/1",
                    "title": "My Song on TIDAL",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher(sites=(_TIDAL_TEST_RULE,)).search(
        artist="a", track="b", max_results=10
    )
    assert hits[0].title == "My Song"


def test_tidal_browse_album_transform_and_dedupe(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://tidal.com/browse/album/411506460",
                    "title": "from browse",
                    "body": "",
                },
                {
                    "href": "https://tidal.com/album/411506460",
                    "title": "canonical",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher(sites=(_TIDAL_TEST_RULE,)).search(
        artist="a", track="b", max_results=10
    )
    assert len(hits) == 1
    assert hits[0].url == "https://tidal.com/album/411506460"
    assert hits[0].title == "from browse"


def test_canonical_url_key_ignores_query() -> None:
    a = _canonical_url_key("https://tidal.com/album/1?utm=x")
    b = _canonical_url_key("https://tidal.com/album/1")
    assert a == b


def test_canonical_url_key_merges_tidal_hosts() -> None:
    a = _canonical_url_key("https://listen.tidal.com/album/411506460")
    b = _canonical_url_key("https://tidal.com/album/411506460")
    assert a == b


def test_browse_artist_exclude_does_not_use_query_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Path is /album/… but query contained '/browse/artist/' — must not drop (regression)."""

    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "href": "https://tidal.com/album/1?redirect=%2Fbrowse%2Fartist%2F99",
                    "title": "album",
                    "body": "",
                },
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = MultiSiteWebSearcher(sites=(_TIDAL_TEST_RULE,)).search(
        artist="a", track="b", max_results=10
    )
    assert len(hits) == 1
    assert "album" in hits[0].url


def test_custom_site_exclude(monkeypatch: pytest.MonkeyPatch) -> None:
    rules = (
        SiteSearchRule(
            domain="example.com",
            url_exclude_patterns=(r"/skip/",),
        ),
    )
    searcher = MultiSiteWebSearcher(sites=rules)

    class FakeDDGS:
        def __enter__(self) -> FakeDDGS:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def text(
            self, query: str, max_results: int = 10, **kwargs: object
        ) -> list[dict[str, str]]:
            return [
                {"href": "https://example.com/skip/nope", "title": "n", "body": ""},
                {"href": "https://example.com/ok", "title": "y", "body": ""},
            ]

    monkeypatch.setattr(wss, "DDGS", FakeDDGS)
    _q, hits = searcher.search(artist="a", track="b", max_results=10)
    assert len(hits) == 1
    assert hits[0].url.endswith("/ok")
