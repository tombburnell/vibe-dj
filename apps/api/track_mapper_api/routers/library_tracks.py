"""Library tracks list (dummy data)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from track_mapper_api.schemas import LibraryTrackOut

router = APIRouter(prefix="/library-tracks", tags=["library-tracks"])

_DUMMY_SNAPSHOT_ID = "00000000-0000-4000-8000-000000000001"
_DUMMY_USER_ID = "dev-user"


def _dummy_library_tracks() -> list[LibraryTrackOut]:
    base = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    return [
        LibraryTrackOut(
            id="11111111-1111-4111-8111-111111111101",
            user_id=_DUMMY_USER_ID,
            library_snapshot_id=_DUMMY_SNAPSHOT_ID,
            title="Untold",
            artist="Octave One",
            album="Summers On Jupiter",
            duration_ms=298000,
            file_path="/Music/Techno/octave_one_untold.mp3",
            bpm=128.0,
            musical_key="Am",
            genre="Techno",
            created_at=base,
        ),
        LibraryTrackOut(
            id="11111111-1111-4111-8111-111111111102",
            user_id=_DUMMY_USER_ID,
            library_snapshot_id=_DUMMY_SNAPSHOT_ID,
            title="Showbiz (Purple Disco Machine Edit)",
            artist="Yuksek feat. Villa",
            album="Showbiz",
            duration_ms=345000,
            file_path="/Music/Disco/yuksek_showbiz_pdm.mp3",
            bpm=122.0,
            musical_key="Dm",
            genre="Nu Disco",
            created_at=base,
        ),
        LibraryTrackOut(
            id="11111111-1111-4111-8111-111111111103",
            user_id=_DUMMY_USER_ID,
            library_snapshot_id=_DUMMY_SNAPSHOT_ID,
            title="Strings of Life",
            artist="Soul Central",
            album=None,
            duration_ms=412000,
            file_path="/Music/House/soul_central_strings.flac",
            bpm=124.0,
            musical_key="Fm",
            genre="House",
            created_at=base,
        ),
    ]


@router.get("", response_model=list[LibraryTrackOut])
def list_library_tracks() -> list[LibraryTrackOut]:
    """Return dummy library rows for UI development."""
    return _dummy_library_tracks()
