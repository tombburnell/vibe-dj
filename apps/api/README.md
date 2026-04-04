# Track Mapper API

FastAPI service implementing [`docs/data-model.md`](../../docs/data-model.md): Postgres-backed library snapshots, playlist/source imports, and matching with persisted `source_library_links`.

## Dependencies

1. Use **[uv](https://github.com/astral-sh/uv)** and **`pyproject.toml` + `uv.lock` only** for this app—**do not** add `requirements.txt`.
2. Install: `uv sync` from `apps/api`.
3. Optional dev helpers (e.g. Starlette `TestClient`): `uv sync --group dev`.

## Configuration

| Variable | Required | Notes |
| -------- | -------- | ----- |
| `DATABASE_URL` | Yes (except tests) | e.g. `postgresql+psycopg://user:pass@localhost:5432/trackmapper` |
| `DEV_USER_ID` | No | Default tenant when `X-Dev-User-Id` header is absent (default `dev-user`). |
| `CORS_ORIGINS` | No | Comma-separated; defaults include Vite dev ports. |

## Database migrations (Postgres)

From `apps/api` with `DATABASE_URL` set:

```bash
uv run alembic upgrade head
```

Initial revision: `001_initial_schema` (tables + partial unique indexes).

## Run (dev)

### Docker (with Postgres + web UI)

From the **repository root**:

```bash
docker compose -f docker-compose.local.yml up
```

Runs Postgres, applies Alembic migrations, FastAPI with `--reload`, and Vite with HMR. See comments in `docker-compose.local.yml` for ports and credentials.

### Local (no Docker)

```bash
cd apps/api
uv sync
export DATABASE_URL=postgresql+psycopg://...
uv run alembic upgrade head
uv run uvicorn track_mapper_api.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI: http://127.0.0.1:8000/docs  
- Optional header: `X-Dev-User-Id: <string>` to override `DEV_USER_ID` for multi-tenant-style tests.

### Main HTTP routes

1. `POST /api/library-snapshots/import` — multipart `file` (Rekordbox TSV), optional `label`.
2. `GET /api/library-tracks` — paginated JSON `{ "items": [...], "next_cursor": "<opaque> | null" }`. Query: `limit` (default 100, max 500), `cursor` (from previous `next_cursor`), optional `snapshot_id`.
3. `GET /api/playlists` — list playlists for the current user.
4. `DELETE /api/playlists/{playlist_id}` — delete playlist and unlink from all source tracks (`source_track_playlists` CASCADE).
5. `POST /api/playlists/import` — multipart `file` (CSV), optional `playlist_name` (defaults to file basename from the part or `client_filename`), optional `client_filename`, optional `import_source`.
6. `GET /api/source-tracks` — flattened source rows with `playlist_names`; `top_match_*` fields are null (use batch endpoint for grid).
7. `POST /api/source-tracks/top-matches` — JSON `{ "source_track_ids": ["<uuid>", ...] }` (max 100) — best match per id vs latest library snapshot.
8. `GET /api/source-tracks/{id}/candidates` — matcher top-K for the secondary panel.
9. `POST /api/match/run` — JSON body optional `library_snapshot_id`, `min_confidence`.

Matching reuses the monorepo [`src/`](../../src) package (`src.track_matching`, `src.rekordbox_index`, `src.rekordbox_tsv_parser`); the API adds the repo root to `sys.path` at runtime.

## Smoke check

```bash
cd apps/api
uv sync --group dev
uv run python -m pytest -q
```

Tests use SQLite in-memory (`conftest.py`) and do not require Postgres.

## CORS

Defaults allow `http://localhost:5173` and `http://127.0.0.1:5173` (Vite). Override with env `CORS_ORIGINS` (comma-separated).
