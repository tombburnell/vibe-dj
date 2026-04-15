"""FastAPI entrypoint."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from track_mapper_api.routers import (
    library_snapshots,
    library_tracks,
    match,
    playlists,
    source_tracks,
    spotify_oauth,
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _configure_track_mapper_logging() -> None:
    """Uvicorn only configures its own loggers; app ``INFO`` logs would otherwise be dropped."""
    log = logging.getLogger("track_mapper_api")
    if log.handlers:
        return
    raw = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, raw, logging.INFO)
    log.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    log.addHandler(handler)
    log.propagate = False


def create_app() -> FastAPI:
    _configure_track_mapper_logging()
    app = FastAPI(
        title="Track Mapper API",
        description="Library import, source playlists, and matching API.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Persisted-Path"],
    )
    app.include_router(library_tracks.router, prefix="/api")
    app.include_router(library_snapshots.router, prefix="/api")
    app.include_router(playlists.router, prefix="/api")
    app.include_router(source_tracks.router, prefix="/api")
    app.include_router(match.router, prefix="/api")
    app.include_router(spotify_oauth.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def run_dev() -> None:
    """CLI entry for `uv run track-mapper-api` (optional)."""
    import uvicorn

    uvicorn.run(
        "track_mapper_api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )


if __name__ == "__main__":
    run_dev()
