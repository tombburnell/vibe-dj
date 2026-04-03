"""Add monorepo root to sys.path so `src.*` legacy modules import correctly."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path() -> Path:
    """Return repo root; insert it on sys.path once (for `src` package imports)."""
    # track_mapper_api -> apps/api -> apps -> repo root
    root = Path(__file__).resolve().parent.parent.parent.parent
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root
