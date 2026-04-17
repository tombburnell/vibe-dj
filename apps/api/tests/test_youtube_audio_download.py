"""YouTube URL parsing and source-track membership checks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from track_mapper_api.services.youtube_audio_download import (
    download_and_transcode_youtube_m4a,
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


def test_download_and_transcode_youtube_m4a_skips_ffmpeg_when_ytdlp_writes_m4a(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "Artist - Title [abcdefghijk].m4a"

    class FakeYoutubeDL:
        def __init__(self, opts: dict[str, object]) -> None:
            self.opts = opts

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def download(self, urls: list[str]) -> None:
            assert urls == ["https://www.youtube.com/watch?v=abcdefghijk"]
            output_file.write_bytes(b"fake m4a bytes")

    def fail_if_called(src: Path, dest: Path) -> None:
        raise AssertionError(f"ffmpeg should not run for {src} -> {dest}")

    monkeypatch.setattr(
        "track_mapper_api.services.youtube_audio_download.yt_dlp.YoutubeDL",
        FakeYoutubeDL,
    )
    monkeypatch.setattr(
        "track_mapper_api.services.youtube_audio_download._ffmpeg_transcode_aac_m4a",
        fail_if_called,
    )

    result = download_and_transcode_youtube_m4a(
        artist="Artist",
        title="Title",
        page_url="https://www.youtube.com/watch?v=abcdefghijk",
        work_dir=tmp_path,
    )

    assert result == output_file
    assert result.read_bytes() == b"fake m4a bytes"
