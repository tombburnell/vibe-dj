#!/usr/bin/env python3
"""Decode an audio file to a PCM WAV next to the source (same basename, ``.wav``).

Usage:
    python scripts/make_wav_version.py <path>

If ``<path>`` is already ``.wav``, prints a short message and exits 0.

Requires ``ffmpeg`` on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        type=Path,
        help="Input audio file",
    )
    args = parser.parse_args()

    src = args.input_path.expanduser().resolve()
    if not src.is_file():
        print(f"Not a file: {src}", file=sys.stderr)
        return 1

    if src.suffix.lower() == ".wav":
        print(f'"{src.name}" is already WAV.')
        return 0

    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found on PATH.", file=sys.stderr)
        return 1

    dest = src.with_suffix(".wav")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-acodec",
        "pcm_s16le",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(
            f"ffmpeg failed for {src}:\n{proc.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    print(f"{src.name} -> {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
