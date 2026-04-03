# Track Mapper API

FastAPI service for [`docs/data-model.md`](../../docs/data-model.md).

## Dependencies

1. Use **[uv](https://github.com/astral-sh/uv)** and **`pyproject.toml` + `uv.lock` only** for this app—**do not** add `requirements.txt`.
2. Install: `uv sync` from `apps/api`.
3. Optional dev helpers (e.g. Starlette `TestClient`): `uv sync --group dev`.

## Run (dev)

```bash
cd apps/api
uv sync
uv run uvicorn track_mapper_api.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI: http://127.0.0.1:8000/docs  
- `GET /api/library-tracks` and `GET /api/source-tracks` return **dummy data** until Postgres is wired.

## Smoke check

```bash
cd apps/api
uv sync --group dev
uv run python -m pytest -q
```

## CORS

Defaults allow `http://localhost:5173` and `http://127.0.0.1:5173` (Vite). Override with env `CORS_ORIGINS` (comma-separated).
