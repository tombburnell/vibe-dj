"""YouTube URL parsing and source-track membership checks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from track_mapper_api.services.youtube_audio_download import (
    source_track_contains_youtube_url,
    youtube_video_id,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
        ("https://m.youtube.com/watch?v=abc12345123", "abc12345123"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtu.be/dQw4w9WgXcQ?t=1", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abcdefghijk", None),
        ("https://music.youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
        ("not a url", None),
        ("https://example.com/watch?v=foo", None),
    ],
)
def test_youtube_video_id(url: str, expected: str | None) -> None:
    assert youtube_video_id(url) == expected


def test_source_track_contains_youtube_url_matches_primary_and_candidates() -> None:
    st = SimpleNamespace(
        amazon_url="https://www.youtube.com/watch?v=abc111defgh",
        amazon_candidates_json=[
            {"url": "https://soundcloud.com/x/y"},
            {"url": "https://youtu.be/zzzzzzzzzzz"},
        ],
    )
    assert source_track_contains_youtube_url(st, "https://youtu.be/abc111defgh") is True
    assert source_track_contains_youtube_url(st, "https://www.youtube.com/watch?v=zzzzzzzzzzz") is True
    assert source_track_contains_youtube_url(st, "https://www.youtube.com/watch?v=otherothero") is False
