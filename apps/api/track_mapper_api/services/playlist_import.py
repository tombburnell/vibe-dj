from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.playlist import Playlist, source_track_playlists
from track_mapper_api.models.source import SourceTrack


@dataclass(frozen=True)
class PlaylistTrackInput:
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    spotify_id: str | None = None


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


def derive_playlist_display_name(
    playlist_name: str | None, upload_filename: str | None
) -> str:
    """Use explicit name if provided; otherwise CSV upload basename; else default label."""
    if playlist_name and playlist_name.strip():
        return playlist_name.strip()
    if upload_filename:
        stem = Path(upload_filename).stem.strip()
        if stem:
            return stem
    return "Imported playlist"


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


async def import_playlist_tracks(
    db: AsyncSession,
    *,
    user_id: str,
    name: str,
    tracks: list[PlaylistTrackInput],
    import_source: str,
    source_kind: str,
    spotify_playlist_id: str | None = None,
) -> tuple[uuid.UUID, int, int]:
    """Create or reuse playlist, upsert source_tracks (Spotify dedupe), attach M2M.

    Re-imports: same Spotify playlist id reuses one row; same CSV name + import_source
    reuses a non-Spotify playlist for that user.

    Returns (playlist_id, rows_attached, new_source_rows).
    """
    display_name = name.strip() if name.strip() else "Imported playlist"

    norm_spotify_pl: str | None = None
    if spotify_playlist_id and spotify_playlist_id.strip():
        raw = spotify_playlist_id.strip()
        norm_spotify_pl = raw[:64] if len(raw) > 64 else raw

    pl: Playlist | None = None
    if norm_spotify_pl is not None:
        res = await db.execute(
            select(Playlist)
            .where(
                Playlist.user_id == user_id,
                Playlist.spotify_playlist_id == norm_spotify_pl,
            )
            .order_by(Playlist.created_at.asc())
            .limit(1)
        )
        pl = res.scalars().first()
        if pl is not None:
            pl.name = display_name

    if pl is None and norm_spotify_pl is None:
        res = await db.execute(
            select(Playlist)
            .where(
                Playlist.user_id == user_id,
                Playlist.name == display_name,
                Playlist.import_source == import_source,
                Playlist.spotify_playlist_id.is_(None),
            )
            .order_by(Playlist.created_at.asc())
            .limit(1)
        )
        pl = res.scalars().first()

    if pl is None:
        pl = Playlist(
            id=uuid.uuid4(),
            user_id=user_id,
            name=display_name,
            import_source=import_source,
            spotify_playlist_id=norm_spotify_pl,
        )
        db.add(pl)
        await db.flush()

    new_sources = 0
    attached = 0
    now = datetime.now(timezone.utc)

    for t in tracks:
        spotify_id = t.spotify_id
        if spotify_id and len(spotify_id) > 64:
            spotify_id = spotify_id[:64]

        if not t.title.strip() and not t.artist.strip():
            continue

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

        title = t.title.strip() or "Unknown Title"
        artist = t.artist.strip() or "Unknown Artist"

        if st is None:
            st = SourceTrack(
                id=uuid.uuid4(),
                user_id=user_id,
                source_kind=source_kind,
                title=title,
                artist=artist,
                album=t.album,
                duration_ms=t.duration_ms,
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


async def import_playlist_csv(
    db: AsyncSession,
    *,
    user_id: str,
    file_bytes: bytes,
    playlist_name: str | None = None,
    upload_filename: str | None = None,
    import_source: str = "chosic_csv",
) -> tuple[uuid.UUID, int, int]:
    """Create playlist, upsert source_tracks (Spotify dedupe), attach M2M.

    Returns (playlist_id, rows_attached, new_source_rows).
    """
    display_name = derive_playlist_display_name(playlist_name, upload_filename)
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return await import_playlist_tracks(
            db,
            user_id=user_id,
            name=display_name,
            tracks=[],
            import_source=import_source,
            source_kind="playlist_csv",
        )

    tracks: list[PlaylistTrackInput] = []
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
        tracks.append(
            PlaylistTrackInput(
                title=title or "",
                artist=artist or "",
                album=album,
                duration_ms=duration_ms,
                spotify_id=spotify_id,
            )
        )

    return await import_playlist_tracks(
        db,
        user_id=user_id,
        name=display_name,
        tracks=tracks,
        import_source=import_source,
        source_kind="playlist_csv",
    )
