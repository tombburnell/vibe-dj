# Track Mapper — Web frontend

Vite + React + TypeScript + Tailwind. See [`docs/UI.md`](../../docs/UI.md) and [`docs/design-system.md`](../../docs/design-system.md).

## Dev

1. Start API (from repo): `cd apps/api && uv run uvicorn track_mapper_api.main:app --reload --port 8000`
2. Install & run UI:

```bash
cd apps/web-frontend
npm install
npm run dev
```

Vite proxies `/api` → `http://127.0.0.1:8000` (see `vite.config.ts`). Optional: copy `.env.example` to `.env` and set `VITE_API_BASE_URL` if the API is elsewhere.

## Build

```bash
npm run build
npm run preview
```

## Structure

- `src/api/` — HTTP client + types (no React)
- `src/hooks/` — Data fetching, theme, density, match demo heuristic
- `src/components/` — Layout, tables, workspace sections
- `src/pages/` — Route-level composition
- `src/providers/` — Toast context
