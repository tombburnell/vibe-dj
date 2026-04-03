from __future__ import annotations

from fastapi import Header, HTTPException

from track_mapper_api.config import get_dev_user_id
from track_mapper_api.db.session import get_session

# Async session per request (commit/rollback inside get_session).
get_db = get_session


def get_current_user_id(
    x_dev_user_id: str | None = Header(None, alias="X-Dev-User-Id"),
) -> str:
    """Resolve tenant user id (Firebase UID later). Header overrides env default."""
    if x_dev_user_id is not None and x_dev_user_id.strip():
        return x_dev_user_id.strip()
    return get_dev_user_id()


def require_database_configured() -> None:
    """Fail fast with 503 if DATABASE_URL missing (optional guard for routes)."""
    from track_mapper_api.config import get_database_url

    try:
        get_database_url()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
