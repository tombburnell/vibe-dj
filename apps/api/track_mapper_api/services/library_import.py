from __future__ import annotations

import hashlib
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.library import LibrarySnapshot, LibraryTrack
from track_mapper_api.repo_src_path import ensure_repo_root_on_path


async def import_rekordbox_tsv(
    db: AsyncSession,
    *,
    user_id: str,
    file_bytes: bytes,
    filename: str | None,
    label: str | None = None,
) -> tuple[uuid.UUID, int]:
    """Parse TSV bytes, create snapshot + library_tracks. Returns (snapshot_id, count)."""
    ensure_repo_root_on_path()
    from src.rekordbox_tsv_parser import RekordboxTSVParser

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    parser = RekordboxTSVParser()

    with tempfile.NamedTemporaryFile(suffix=".tsv", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        parsed = parser.parse_tsv(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    snap = LibrarySnapshot(
        id=uuid.uuid4(),
        user_id=user_id,
        label=label or (filename or "Rekordbox import"),
        source_filename=filename,
        content_hash=content_hash,
    )
    db.add(snap)
    await db.flush()

    count = 0
    for row in parsed:
        db.add(
            LibraryTrack(
                id=uuid.uuid4(),
                user_id=user_id,
                library_snapshot_id=snap.id,
                title=row.title,
                artist=row.artist,
                album=row.album,
                duration_ms=row.duration_ms,
                file_path=row.file_path or "",
                bpm=row.bpm,
                musical_key=row.key,
                genre=row.genre,
                tags=None,
            )
        )
        count += 1

    return snap.id, count
