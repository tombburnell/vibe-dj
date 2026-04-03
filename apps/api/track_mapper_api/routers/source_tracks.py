"""Source tracks list (dummy data)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from track_mapper_api.schemas import SourceTrackOut

router = APIRouter(prefix="/source-tracks", tags=["source-tracks"])

_DUMMY_USER_ID = "dev-user"


def _dummy_source_tracks() -> list[SourceTrackOut]:
    t0 = datetime(2026, 1, 10, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 12, 15, 30, 0, tzinfo=UTC)
    return [
        SourceTrackOut(
            id="22222222-2222-4222-8222-222222222201",
            user_id=_DUMMY_USER_ID,
            source_kind="playlist_csv",
            title="Untold",
            artist="Octave One",
            album="Summers On Jupiter",
            duration_ms=298000,
            spotify_id="0sQDaCCZDNsdSBnP66Z8BN",
            spotify_url="https://open.spotify.com/track/0sQDaCCZDNsdSBnP66Z8BN",
            on_wishlist=True,
            playlist_names=["Koko Groove", "Peak Time"],
            local_file_path=None,
            downloaded_at=None,
            amazon_url=None,
            amazon_search_url="https://www.amazon.com/s?k=Octave+One+Untold",
            created_at=t0,
            updated_at=t0,
        ),
        SourceTrackOut(
            id="22222222-2222-4222-8222-222222222202",
            user_id=_DUMMY_USER_ID,
            source_kind="playlist_csv",
            title="Showbiz Feat. Villa",
            artist="Yuksek",
            album="Showbiz",
            duration_ms=340000,
            spotify_id="4iV7Q9b7V5Q5Q5Q5Q5Q5Q5Q",
            spotify_url="https://open.spotify.com/track/4iV7Q9b7V5Q5Q5Q5Q5Q5Q5Q",
            on_wishlist=True,
            playlist_names=["Koko Groove"],
            local_file_path="/Downloads/yuksek_showbiz.m4a",
            downloaded_at=t1,
            amazon_url="https://music.amazon.com/albums/B00XXXX",
            amazon_search_url=None,
            created_at=t0,
            updated_at=t1,
        ),
        SourceTrackOut(
            id="22222222-2222-4222-8222-222222222203",
            user_id=_DUMMY_USER_ID,
            source_kind="manual",
            title="Obscure B-Side",
            artist="Unknown Artist",
            album=None,
            duration_ms=None,
            spotify_id=None,
            spotify_url=None,
            on_wishlist=True,
            playlist_names=[],
            local_file_path=None,
            downloaded_at=None,
            amazon_url=None,
            amazon_search_url=None,
            created_at=t1,
            updated_at=t1,
        ),
        SourceTrackOut(
            id="22222222-2222-4222-8222-222222222204",
            user_id=_DUMMY_USER_ID,
            source_kind="playlist_csv",
            title="Strings of Life",
            artist="Soul Central",
            album=None,
            duration_ms=410000,
            spotify_id="3jHidbU049dUQ5mIOx20jH",
            spotify_url="https://open.spotify.com/track/3jHidbU049dUQ5mIOx20jH",
            on_wishlist=False,
            playlist_names=["Reference Only"],
            local_file_path=None,
            downloaded_at=None,
            amazon_url=None,
            amazon_search_url=None,
            created_at=t1,
            updated_at=t1,
        ),
    ]


@router.get("", response_model=list[SourceTrackOut])
def list_source_tracks() -> list[SourceTrackOut]:
    """Return dummy source rows for UI development."""
    return _dummy_source_tracks()
