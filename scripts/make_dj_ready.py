#!/usr/bin/env python3
"""Prepare audio files for DJ use: outputs are only ``.mp3`` or ``.m4a``.

**Output rule:** ``mp3 → mp3`` (copy). **Anything else → m4a** — already-``m4a``
sources are copied; all other supported formats are transcoded to AAC in ``.m4a``.

Usage:
    python scripts/make_dj_ready.py <input_path> [<output_dir>]

``input_path`` may be a **directory** (top-level audio files only) or one **audio file**.

If <output_dir> is omitted, uses ``<parent>/dj_ready`` (parent = input directory, or
the file's directory when input is a file).

**Loudness (optional, mutually exclusive):**

- ``--norm`` — two-pass EBU loudnorm to **-16 LUFS** (true peak -1.5 dBTP, LRA 11).
- ``--loud N`` — two-pass loudnorm to **-abs(N) LUFS** (e.g. ``--loud 12`` and
  ``--loud -12`` both target **-12** LUFS).

With ``--norm`` / ``--loud``, sources are always run through ffmpeg (no byte copy).

``--force`` — do not skip when the target (or sibling mp3/m4a slot) exists; overwrite
the chosen output path. For a single source per ``<base>``, the primary
``<base>.mp3`` / ``<base>.m4a`` is overwritten.

Skips processing when ``<base>.mp3`` or ``<base>.m4a`` already exists (unless
``--force``). Multiple sources sharing the same ``<base>`` get ``<base>_2.*``, etc.

Requires ``ffmpeg`` and ``ffprobe`` on PATH.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


AUDIO_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".m4a",
        ".aac",
        ".mp4",
        ".wav",
        ".flac",
        ".aiff",
        ".aif",
        ".ogg",
        ".opus",
        ".wma",
        ".mka",
        ".webm",
        ".mpa",
    }
)

# Only mp3/m4a are ever written; used for collision / skip detection.
_OUTPUT_SUFFIXES = frozenset({".m4a", ".mp3"})

NORM_DEFAULT_I = -16.0
NORM_DEFAULT_TP = -1.5
NORM_DEFAULT_LRA = 11.0


@dataclass(frozen=True)
class LoudnormTarget:
    integrated: float
    true_peak: float = NORM_DEFAULT_TP
    lra: float = NORM_DEFAULT_LRA


def _run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    return json.loads(proc.stdout or "{}")


def ffprobe_data(path: Path) -> dict:
    return _run_json(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )


def _tag_lookup(tags: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        for variant in (key, key.upper(), key.lower(), key.capitalize()):
            if variant in tags and tags[variant].strip():
                return tags[variant].strip()
    return None


def _collect_tags(data: dict) -> dict[str, str]:
    merged: dict[str, str] = {}
    fmt_tags = (data.get("format") or {}).get("tags") or {}
    if isinstance(fmt_tags, dict):
        merged.update({str(k): str(v) for k, v in fmt_tags.items()})
    for stream in data.get("streams") or []:
        st = stream.get("tags") or {}
        if isinstance(st, dict):
            for k, v in st.items():
                merged.setdefault(str(k), str(v))
    return merged


def title_artist_from_probe(path: Path) -> tuple[str, str]:
    try:
        data = ffprobe_data(path)
    except (RuntimeError, json.JSONDecodeError):
        return path.stem, ""

    tags = _collect_tags(data)
    title = _tag_lookup(tags, "title", "TITLE", "Title")
    artist = _tag_lookup(tags, "artist", "ARTIST", "Artist")
    if not artist:
        artist = _tag_lookup(
            tags, "album_artist", "ALBUM_ARTIST", "album artist", "AlbumArtist"
        )

    if not title:
        title = path.stem
    if not artist:
        artist = ""
    return title, artist


def sanitize_base_part(s: str) -> str:
    s = s.strip()
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .")


def build_base_name(path: Path) -> str:
    title, artist = title_artist_from_probe(path)
    t = sanitize_base_part(title)
    a = sanitize_base_part(artist)
    if a:
        base = f"{t}-{a}"
    else:
        base = t
    base = base.strip("- ")
    if not base:
        base = sanitize_base_part(path.stem) or "track"
    return base


def scan_occupied_slots(output_dir: Path) -> set[Path]:
    """Resolved paths of existing outputs (excludes incomplete ``*.tmp.m4a``)."""
    occupied: set[Path] = set()
    try:
        for p in output_dir.iterdir():
            if not p.is_file():
                continue
            if p.name.endswith(".tmp.m4a"):
                continue
            if p.suffix.lower() not in _OUTPUT_SUFFIXES:
                continue
            try:
                occupied.add(p.resolve())
            except OSError:
                continue
    except OSError:
        pass
    return occupied


def first_free_path(
    output_dir: Path, base: str, ext: str, occupied: set[Path]
) -> Path:
    """First ``base[_{n}].ext`` whose resolved path is not in ``occupied``."""
    candidate = output_dir / f"{base}{ext}"
    if candidate.resolve() not in occupied:
        return candidate
    n = 2
    while n < 100_000:
        alt = output_dir / f"{base}_{n}{ext}"
        if alt.resolve() not in occupied:
            return alt
        n += 1
    raise RuntimeError(f"Could not allocate output path for {base}{ext}")


def existing_mp3_or_m4a(output_dir: Path, base: str) -> Path | None:
    for ext in (".mp3", ".m4a"):
        p = output_dir / f"{base}{ext}"
        if p.is_file():
            return p
    return None


def print_track_line(src: Path, fmt: str, target: Path) -> None:
    print(f"{src.resolve()} -> {fmt} -> {target.resolve()}")


def is_copy_format(suffix: str) -> tuple[bool, str]:
    """mp3 → mp3 copy; m4a → m4a copy; any other suffix → not copy (encode to m4a)."""
    s = suffix.lower()
    if s == ".mp3":
        return True, ".mp3"
    if s == ".m4a":
        return True, ".m4a"
    return False, ""


def ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing `{name}` on PATH; install ffmpeg.")


def _parse_loudnorm_json(stderr: str) -> dict[str, object]:
    start = stderr.rfind("{")
    if start == -1:
        raise RuntimeError("loudnorm did not emit JSON (no '{' in ffmpeg stderr)")
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(stderr[start:])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"loudnorm JSON parse failed: {e}") from e
    if not isinstance(obj, dict):
        raise RuntimeError("loudnorm JSON root must be an object")
    return obj


def build_loudnorm_af(src: Path, target: LoudnormTarget) -> str:
    """Two-pass loudnorm: measure, then return the linear second-pass filter string."""
    i, tp, lra = target.integrated, target.true_peak, target.lra
    pass1_af = f"loudnorm=I={i}:TP={tp}:LRA={lra}:print_format=json"
    cmd1 = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-i",
        str(src),
        "-af",
        pass1_af,
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd1, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"loudnorm measure failed for {src}:\n{proc.stderr.strip()}"
        )
    j = _parse_loudnorm_json(proc.stderr)
    try:
        mi = j["input_i"]
        mtp = j["input_tp"]
        mlra = j["input_lra"]
        mth = j["input_thresh"]
        off = j["target_offset"]
    except KeyError as e:
        raise RuntimeError(f"loudnorm JSON missing key {e!s}: {j!r}") from e
    return (
        f"loudnorm=linear=true:I={i}:TP={tp}:LRA={lra}"
        f":measured_I={mi}:measured_LRA={mlra}:measured_TP={mtp}"
        f":measured_thresh={mth}:offset={off}"
    )


def convert_to_m4a(src: Path, dest: Path, af: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.m4a")
    tmp.unlink(missing_ok=True)
    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
    ]
    if af:
        cmd += ["-af", af]
    cmd += [
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-f",
        "mp4",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg failed for {src}:\n{proc.stderr.strip()}")
    tmp.replace(dest)


def transcode_to_mp3(src: Path, dest: Path, af: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.mp3")
    tmp.unlink(missing_ok=True)
    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
    ]
    if af:
        cmd += ["-af", af]
    cmd += ["-c:a", "libmp3lame", "-q:a", "0", str(tmp)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg failed for {src}:\n{proc.stderr.strip()}")
    tmp.replace(dest)


def copy_to(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def iter_audio_files(root: Path) -> list[Path]:
    root = root.resolve()
    out: list[Path] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    for path in children:
        if not path.is_file():
            continue
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        out.append(path)
    return sorted(out)


def resolve_input_files(input_path: Path) -> tuple[list[Path], Path]:
    """Return (audio files, default_output_parent)."""
    p = input_path.expanduser().resolve()
    if p.is_file():
        if p.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError(f"Not a supported audio file: {p}")
        return [p], p.parent
    if p.is_dir():
        return iter_audio_files(p), p
    raise ValueError(f"Not a file or directory: {p}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        type=Path,
        help="Audio file or directory (dir: top-level files only)",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=None,
        help="Output directory (default: <parent>/dj_ready)",
    )
    parser.add_argument(
        "--norm",
        action="store_true",
        help=(
            f"Two-pass loudnorm to {NORM_DEFAULT_I} LUFS "
            f"(TP {NORM_DEFAULT_TP}, LRA {NORM_DEFAULT_LRA})"
        ),
    )
    parser.add_argument(
        "--loud",
        type=int,
        default=None,
        metavar="N",
        help="Two-pass loudnorm to -abs(N) LUFS (e.g. 12 and -12 → -12)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite outputs instead of skipping when target exists",
    )
    args = parser.parse_args()

    if args.norm and args.loud is not None:
        print("Use either --norm or --loud, not both.", file=sys.stderr)
        return 2

    loud_target: LoudnormTarget | None
    if args.norm:
        loud_target = LoudnormTarget(integrated=NORM_DEFAULT_I)
    elif args.loud is not None:
        loud_target = LoudnormTarget(integrated=-abs(float(args.loud)))
    else:
        loud_target = None

    try:
        files, default_parent = resolve_input_files(args.input_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir is not None
        else (default_parent / "dj_ready")
    )

    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")

    if not files:
        print(f"No audio files found for {args.input_path.resolve()}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    entries = [(src, build_base_name(src)) for src in files]
    base_counts = Counter(b for _, b in entries)
    occupied = scan_occupied_slots(output_dir)
    force: bool = args.force

    for src, base in entries:
        if not force:
            blocker = existing_mp3_or_m4a(output_dir, base)
            if blocker is not None:
                print_track_line(src, "skip (mp3/m4a already present)", blocker)
                continue

        copy_ok, copy_ext = is_copy_format(src.suffix)
        use_ffmpeg = loud_target is not None or not copy_ok
        af: str | None = None
        if loud_target is not None:
            af = build_loudnorm_af(src, loud_target)

        if copy_ok and not use_ffmpeg:
            if base_counts[base] == 1:
                dest = output_dir / f"{base}{copy_ext}"
                if not force and dest.resolve() in occupied:
                    print_track_line(src, "skip (copy target already present)", dest)
                    continue
            else:
                dest = first_free_path(output_dir, base, copy_ext, occupied)
            occupied.add(dest.resolve())
            print_track_line(src, f"copy {copy_ext}", dest)
            copy_to(src, dest)
            continue

        out_ext = copy_ext if copy_ok else ".m4a"
        if base_counts[base] == 1:
            dest = output_dir / f"{base}{out_ext}"
            if not force and dest.resolve() in occupied:
                print_track_line(src, "skip (output already present)", dest)
                continue
        else:
            dest = first_free_path(output_dir, base, out_ext, occupied)

        occupied.add(dest.resolve())
        if loud_target is not None:
            fmt_mid = (
                f"loudnorm I={loud_target.integrated} LUFS TP={loud_target.true_peak}"
            )
        elif out_ext == ".mp3":
            fmt_mid = "encode libmp3lame V0"
        else:
            fmt_mid = "encode AAC 320k m4a"

        print_track_line(src, fmt_mid, dest)
        try:
            if out_ext == ".mp3":
                transcode_to_mp3(src, dest, af)
            else:
                convert_to_m4a(src, dest, af)
        except RuntimeError as e:
            occupied.discard(dest.resolve())
            print(
                f"({src.resolve()}) -> ERROR ({e}) -> ({dest.resolve()})",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
