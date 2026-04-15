"""Download audio from YouTube via yt-dlp, transcode to AAC ``.m4a`` for wide hardware support."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yt_dlp

from track_mapper_api.config import get_repo_root
from track_mapper_api.models.source import SourceTrack

logger = logging.getLogger(__name__)


def youtube_video_id(url: str) -> str | None:
    """Extract the video id when ``url`` is a known YouTube watch/embed URL (not Shorts)."""
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        p = urlparse(raw)
        host = (p.netloc or "").lower().split(":")[0].removeprefix("www.")
    except Exception:
        return None
    if not host:
        return None
    path = p.path or ""

    if host == "youtu.be":
        seg = path.strip("/").split("/")[0]
        return seg if 6 <= len(seg) <= 32 else None

    if host == "youtube.com" or host.endswith(".youtube.com"):
        if path.startswith("/watch"):
            ids = parse_qs(p.query).get("v", [])
            vid = ids[0].strip() if ids and ids[0] else ""
            return vid if 6 <= len(vid) <= 32 else None
        if path.startswith("/shorts/"):
            return None
        if path.startswith("/embed/"):
            seg = path.removeprefix("/embed/").strip("/").split("/")[0]
            return seg if 6 <= len(seg) <= 32 else None
    return None


def is_youtube_page_url(url: str) -> bool:
    return youtube_video_id(url) is not None


def source_track_contains_youtube_url(st: SourceTrack, url: str) -> bool:
    want = youtube_video_id(url)
    if not want:
        return False
    urls: list[str] = []
    if (st.amazon_url or "").strip():
        urls.append(st.amazon_url.strip())
    raw = st.amazon_candidates_json
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                u = item.get("url")
                if isinstance(u, str) and u.strip():
                    urls.append(u.strip())
    for u in urls:
        if youtube_video_id(u) == want:
            return True
    return False


def _safe_filename_stem(artist: str, title: str, video_id: str) -> str:
    base = f"{artist} - {title}".strip() or "track"
    safe = re.sub(r'[^\w\s\-.]', "", base, flags=re.UNICODE)
    safe = re.sub(r"\s+", " ", safe).strip()
    if not safe:
        safe = "track"
    if len(safe) > 160:
        safe = safe[:160].rstrip()
    return f"{safe} [{video_id}]"


def relative_audio_path_from_absolute(abs_path: Path) -> str:
    root = get_repo_root().resolve()
    try:
        rel = abs_path.resolve().relative_to(root)
    except ValueError:
        return abs_path.resolve().as_posix()
    return rel.as_posix()


def _pick_ytdlp_output_file(stem_name: str, work_dir: Path) -> Path:
    prefix = stem_name
    candidates = [
        p
        for p in work_dir.iterdir()
        if p.is_file() and p.name.startswith(prefix + ".") and not p.name.endswith(".part")
    ]
    if not candidates:
        raise RuntimeError("yt-dlp finished but no media file was written")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _ffmpeg_transcode_aac_m4a(src: Path, dest: Path) -> None:
    """AAC-LC in MP4 container (``.m4a``) for DJ decks and phones."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg is not installed or not on PATH") from e
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        logger.error("ffmpeg failed: %s", err[:2000])
        raise RuntimeError("ffmpeg transcoding failed") from e


def download_and_transcode_youtube_m4a(
    *,
    artist: str,
    title: str,
    page_url: str,
    work_dir: Path,
) -> Path:
    """Download best audio with yt-dlp, transcode to ``.m4a`` in ``work_dir``. Returns path to m4a."""
    vid = youtube_video_id(page_url)
    if not vid:
        raise ValueError("Not a supported YouTube URL")
    work_dir.mkdir(parents=True, exist_ok=True)
    stem = work_dir / _safe_filename_stem(artist, title, vid)
    stem_str = str(stem)

    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": stem_str + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "socket_timeout": 120,
        "retries": 3,
    }
    logger.info("yt-dlp download start video_id=%s", vid)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([page_url])
    except Exception:
        logger.exception("yt-dlp failed url=%s", page_url)
        raise

    raw = _pick_ytdlp_output_file(stem.name, work_dir)
    m4a_out = stem.with_suffix(".m4a")
    logger.info("transcoding %s -> %s", raw.suffix, m4a_out.name)
    _ffmpeg_transcode_aac_m4a(raw, m4a_out)
    try:
        raw.unlink(missing_ok=True)
    except OSError:
        logger.warning("could not remove temp download %s", raw)

    if not m4a_out.is_file():
        raise RuntimeError("Transcode did not produce an m4a file")
    logger.info("wrote %s", m4a_out)
    return m4a_out


def copy_m4a_to_library_dir(m4a_path: Path, dest_dir: Path) -> Path:
    """Copy ``m4a_path`` into ``dest_dir`` (same basename)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / m4a_path.name
    shutil.copy2(m4a_path, final)
    return final
