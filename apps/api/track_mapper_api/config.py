from __future__ import annotations

import os
from functools import lru_cache


@lru_cache
def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: postgresql+psycopg://user:pass@localhost:5432/trackmapper",
        )
    return url


def clear_config_cache() -> None:
    get_database_url.cache_clear()


def get_dev_user_id() -> str:
    return os.environ.get("DEV_USER_ID", "dev-user").strip() or "dev-user"
