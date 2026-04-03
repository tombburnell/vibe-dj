from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.playlist import Playlist, source_track_playlists
from track_mapper_api.models.source import SourceTrack


async def _source_playlist_link_exists(
    db: AsyncSession, *, source_track_id: uuid.UUID, playlist_id: uuid.UUID
) -> bool:
    res = await db.execute(
        select(source_track_playlists.c.source_track_id).where(
            source_track_playlists.c.source_track_id == source_track_id,
            source_track_playlists.c.playlist_id == playlist_id,
        )
    )
    return res.first() is not None


def _norm_key(h: str) -> str:
    return h.strip().lower().replace(" ", "_")


def _get(row: dict[str, str], *candidates: str) -> str:
    for rk, rv in row.items():
        nk = _norm_key(rk)
        for c in candidates:
            if nk == _norm_key(c):
                return (rv or "").strip()
    return ""


def parse_duration_ms(val: str) -> int | None:
    if not val or not val.strip():
        return None
    s = val.strip()
    if ":" in s:
        parts = s.split(":")
        try:
            if len(parts) == 2:
                return (int(parts[0]) * 60 + int(parts[1])) * 1000
            if len(parts) == 3:
                return (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
        except ValueError:
            return None
    try:
        return int(float(s) * 1000)
    except ValueError:
        return None


async def import_playlist_csv(
    db: AsyncSession,
    *,
    user_id: str,
    file_bytes: bytes,
    playlist_name: str,
    import_source: str = "chosic_csv",
) -> tuple[uuid.UUID, int, int]:
    """Create playlist, upsert source_tracks (Spotify dedupe), attach M2M.

    Returns (playlist_id, rows_attached, new_source_rows).
    """
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        pl = Playlist(
            id=uuid.uuid4(),
            user_id=user_id,
            name=playlist_name,
            import_source=import_source,
        )
        db.add(pl)
        await db.flush()
        return pl.id, 0, 0

    pl = Playlist(
        id=uuid.uuid4(),
        user_id=user_id,
        name=playlist_name,
        import_source=import_source,
    )
    db.add(pl)
    await db.flush()

    new_sources = 0
    attached = 0
    now = datetime.now(timezone.utc)

    for row in reader:
        title = _get(row, "song", "title", "track", "track_title", "name")
        artist = _get(row, "artist", "artists")
        album = _get(row, "album") or None
        duration_raw = _get(row, "duration", "length", "time")
        spotify_id = _get(row, "spotify_track_id", "spotify id", "spotify_id", "id") or None
        if spotify_id and len(spotify_id) > 64:
            spotify_id = spotify_id[:64]

        if not title and not artist:
            continue

        duration_ms = parse_duration_ms(duration_raw)
        spotify_url = (
            f"https://open.spotify.com/track/{spotify_id}" if spotify_id else None
        )

        st: SourceTrack | None = None
        if spotify_id:
            res = await db.execute(
                select(SourceTrack).where(
                    SourceTrack.user_id == user_id,
                    SourceTrack.spotify_id == spotify_id,
                )
            )
            st = res.scalar_one_or_none()

        if st is None:
            st = SourceTrack(
                id=uuid.uuid4(),
                user_id=user_id,
                source_kind="playlist_csv",
                title=title or "Unknown Title",
                artist=artist or "Unknown Artist",
                album=album,
                duration_ms=duration_ms,
                spotify_id=spotify_id,
                spotify_url=spotify_url,
                on_wishlist=True,
                created_at=now,
                updated_at=now,
            )
            db.add(st)
            await db.flush()
            new_sources += 1
        else:
            st.updated_at = now

        if not await _source_playlist_link_exists(
            db, source_track_id=st.id, playlist_id=pl.id
        ):
            await db.execute(
                insert(source_track_playlists).values(
                    source_track_id=st.id,
                    playlist_id=pl.id,
                )
            )
            attached += 1

    return pl.id, attached, new_sources
