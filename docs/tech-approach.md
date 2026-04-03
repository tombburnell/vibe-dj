# Track Mapper — Technical Approach (current)

> Implementation direction for the **hosted web product** described in [`top_level_spec.md`](./top_level_spec.md). Legacy CLI + SQLite detail lives in [`old/tech-approach.md`](./old/tech-approach.md); archived functional requirements in [`old/old_reqs.md`](./old/old_reqs.md).

## 1. Stack: Python backend + React (Vite) frontend

### 1.1 Why Python on the server

1. **Matching and imports today** — Normalization, fuzzy scoring, Rekordbox **TSV** parsing, inverted-index style search, and Amazon/HTTP flows already exist in `src/`; evolve them behind a real API instead of rewriting.
2. **Likely extensions** — **Direct Rekordbox reads** (e.g. **pyrekordbox** / database formats beyond export files), **audio** processing (previews, BPM/key from signal, fingerprinting), and **ML** (batch or inline) are all **stronger in Python** than in Node for typical libraries and research tooling.
3. **API shape** — **FastAPI** (or similar) exposing REST (or tRPC-style JSON) + **Firebase ID token** verification on protected routes; long-running match jobs can move to **background workers** (same repo, second process or queue later).

### 1.2 Why React with Vite (not Next.js as the primary UI)

1. **UI needs** — Dense **tables** (filtering, virtualization, keyboard UX), **docked secondary panels** for match review (Rekordbox-style), and later **audio** previews benefit from the **largest** React ecosystem (**TanStack Table**, **Radix/shadcn**, Tailwind—see [`design-system.md`](./design-system.md) and [`UI.md`](./UI.md)).
2. **Vite** — Fast dev server, simple **SPA** build output (static `dist/`), easy to serve behind **nginx/Caddy** in the same Docker image as the API.
3. **Separation** — Clear boundary: **React app** = presentation + client state; **Python** = authz, persistence, matching, file uploads, Rekordbox/audio/ML.

### 1.3 TypeScript on the frontend

1. **TypeScript** for the Vite/React app end-to-end (components, API client). Optionally generate or hand-maintain **OpenAPI → types** from FastAPI for request/response shapes.

## 2. Deployment: single Docker image

1. **Goal:** One deployable unit for **Fly.io**, **Hetzner VM**, or similar (see [`top_level_spec.md`](./top_level_spec.md) §9).
2. **Shape:** One container running:
   1. **Python** — `uvicorn` (or gunicorn+uvicorn workers) for the API.
   2. **Static UI** — Vite production build served by **Caddy/nginx** (or FastAPI `StaticFiles` for simplicity in v1) on a single external **:80**/**:443**, with `/api` (or separate host path) proxied to the app server.
3. **Alternative later:** Split browser → CDN static + API subdomain; still compatible with the same codebase and build artifacts.

## 3. Data layer (multi-user)

1. **Tenancy:** Every row keyed by `user_id` (Firebase UID).
2. **Phase 1 recommendation:** **PostgreSQL** accessed from **Python** (**SQLAlchemy 2** + **Alembic**, or equivalent). Keeps ORM and migrations next to matching code.
3. **`apps/api`** — FastAPI app; dependencies only via **`uv`** + **`apps/api/pyproject.toml`** and **`uv.lock`** (no `requirements.txt`). Run `uv sync` from `apps/api`; `uv sync --group dev` for pytest/httpx.
4. **`apps/web-frontend`** — Vite + React + Tailwind; **`npm install`** / **`npm run dev`**. Proxies `/api` to FastAPI in dev (`vite.config.ts`). See `apps/web-frontend/README.md`.
5. **Schema:** **`library_snapshots`**, **`library_tracks`**, **`source_tracks`**, **`playlists`**, **`source_track_playlists`**, **`source_library_links`** — see [`data-model.md`](./data-model.md).
6. **Library snapshots & match decisions:** Aligned with [`top_level_spec.md`](./top_level_spec.md) §7 (`library_snapshot_id`, durable confirm/reject/pick-alternative).
7. **Search:** **Postgres FTS** / **`pg_trgm`** for catalog search and LLM `search_library`-style tools; same role as the legacy inverted index described in [`old/tech-approach.md`](./old/tech-approach.md).

## 4. Authentication

1. **Firebase Authentication** in the React app; attach **ID token** (`Authorization: Bearer`) to API calls.
2. **Python** verifies tokens (Firebase Admin SDK or JWKS against Google’s certs) on each protected route; no Firebase **secrets** in the Vite bundle.

## 5. LLM-assisted matching (when implemented)

1. Follow [`top_level_spec.md`](./top_level_spec.md) §8: small **top-K** candidate sets, optional **search_library** tool—not full-catalog prompts.
2. **Python** SDKs (`openai`, `anthropic`, etc.) from the API or workers; same process as matching.
3. Reference prompt shape: [`chatgpt_matching_prompt.md`](./chatgpt_matching_prompt.md).

## 6. Document map

| Doc | Role |
| --- | ---- |
| [`top_level_spec.md`](./top_level_spec.md) | Product requirements, snapshots, reject semantics |
| [`data-model.md`](./data-model.md) | Postgres tables, links, playlists |
| [`UI.md`](./UI.md) | Routes, layout, primary/secondary panels |
| [`design-system.md`](./design-system.md) | Themes, Tailwind, Radix/shadcn, tables |
| [`tech-approach.md`](./tech-approach.md) | This file — current engineering approach |
| [`old/tech-approach.md`](./old/tech-approach.md) | Legacy SQLite, inverted index, `mm` CLI (algorithms + schema history) |
| [`old/old_reqs.md`](./old/old_reqs.md) | Archived use cases & AC (CLI MVP) |
