"""Paginated library track listing (keyset cursor on file_path + id)."""

from __future__ import annotations

import base64
import json
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.library import LibraryTrack

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


def encode_library_cursor(file_path: str, track_id: uuid.UUID) -> str:
    payload = {"p": file_path, "i": str(track_id)}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_library_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    try:
        pad = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + pad)
        obj = json.loads(raw.decode("utf-8"))
        return str(obj["p"]), uuid.UUID(str(obj["i"]))
    except Exception as e:
        raise ValueError("Invalid cursor") from e


async def load_library_tracks_page(
    db: AsyncSession,
    *,
    user_id: str,
    library_snapshot_id: uuid.UUID,
    limit: int,
    cursor: str | None,
) -> tuple[list[LibraryTrack], str | None]:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    q = select(LibraryTrack).where(
        LibraryTrack.user_id == user_id,
        LibraryTrack.library_snapshot_id == library_snapshot_id,
    )
    if cursor:
        c_path, c_id = decode_library_cursor(cursor)
        q = q.where(
            or_(
                LibraryTrack.file_path > c_path,
                and_(LibraryTrack.file_path == c_path, LibraryTrack.id > c_id),
            )
        )
    q = q.order_by(LibraryTrack.file_path, LibraryTrack.id).limit(limit + 1)
    result = await db.execute(q)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_library_cursor(last.file_path, last.id)
    return page, next_cursor
