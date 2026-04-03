# Track Mapper — UI Specification

> Information architecture, screens, and interaction patterns for [`apps/web-frontend`](../apps/web-frontend). Visual tokens and components: [`design-system.md`](./design-system.md). Product rules: [`top_level_spec.md`](./top_level_spec.md). Persistence: [`data-model.md`](./data-model.md).

## 1. Purpose

1. Single reference for **routes**, **layout**, and **user-visible flows** before and during implementation.
2. Implementation lives under **`apps/web-frontend`**; API contract evolves under **`apps/api`** (endpoints can start as TBD).

## 2. Personas & jobs (short)

1. **DJ / curator** — Compare **wishlist** to **library** and **downloaded** files; confirm or fix matches; open purchase links for **missing** tracks.
2. Glossary: **In library**, **Downloaded**, **Wishlist**, **Missing** — see [`top_level_spec.md`](./top_level_spec.md) §4.

## 3. Hosting & URLs

1. **App origin** — SPA served at **`https://app.<domain>/`** with the **main shell at `/`** (no `/app` path prefix for the primary experience).
2. **Marketing** — **`https://www.<domain>`** (or apex) is a **promo / landing** site that **links or redirects** users to `app.`.
3. **Router** — React Router (or equivalent): authenticated **main workspace** uses **`/`** as the root route after login.

## 4. Authentication

1. **Guard** — Unauthenticated users **never** see the main workspace (no shell, no empty tables). Only **login / signup** (or Firebase-hosted UI) until session valid.
2. **Firebase** — ID token attached to API calls per [`tech-approach.md`](./tech-approach.md) §4.

## 5. Global layout (authenticated)

1. **Single-page workspace** — Not a traditional multi-page sidebar nav; one **primary view** with **filters/tabs** and optional **saved views** (see §7).
2. **Primary region** — **One main table** occupying most of the viewport: shows tracks according to active **filter/tab** (wishlist, downloaded, in library, missing, or combinations as product allows).
3. **Secondary region** — **Docked panel** (Rekordbox/Ableton-style), **not** an overlay drawer:
   1. **Placement** — **Right side** or **below** the main table (product picks one default; optional user resize later).
   2. **Content modes** — Contextual:
      1. **Match candidates** — When a row is selected in the main table, secondary table lists **top-K matches** / library rows for review (confirm, pick another row, reject—actions defined with API).
      2. **Library browse** — When the main table shows a **playlist/wishlist**, secondary can show **library** (or other contextual list) for cross-reference.
   3. **No modal** for core match review in v1 — **faster for pro users** than blocking dialogs.
4. **Header** — Compact: app name, **density** toggle, **theme** toggle, user menu, **Settings** entry.

## 6. Primary table: filters & tabs

1. **Tabs or filter bar** — Switch logical datasets: e.g. **Wishlist**, **Downloaded**, **In library**, **Missing** (exact set aligned with [`top_level_spec.md`](./top_level_spec.md) §4).
2. **Toggle** — Show/hide wishlist rows **already owned** (see product spec **Missing** vs full wishlist).
3. **Saved views** — Later: persist **named filter combinations** (columns/filters); structure the UI so a **“Views”** control can be added without rewriting the table.

## 7. Density & theme

1. **Density** — **Comfortable / compact / ultra-compact** (or three named presets) from **day one** — see [`design-system.md`](./design-system.md) §5.
2. **Theme** — **Dark (default)** and **light**; CSS variables — see [`design-system.md`](./design-system.md) §3.

## 8. Loading & errors

1. **Loading** — **Skeleton** table (rows/cells) for main and secondary tables when data is fetching.
2. **Errors** — **Toasts** for API failures and global messages; non-blocking. Inline errors for form validation where applicable.

## 9. Screens / route map (v1)

| # | Route | Purpose |
| --- | ----- | ------- |
| R1 | `/login` (or Firebase redirect) | Auth only; no app chrome behind guard |
| R2 | `/` | Main workspace: primary table + secondary panel + header |
| R3 | `/settings` | Theme, density, font scale, account-related prefs |
| R4 | Optional `/imports` | If imports are not folded into `/` toolbar/modal flow |

**Note:** Exact path names can match router config; **R2** is the default post-login.

## 10. Flows (v1)

1. **Login** → land on **`/`** with main table empty or populated per API.
2. **Select main row** → secondary panel loads **candidates** or contextual list; user **confirms** / **picks row** / **reject** (per [`top_level_spec.md`](./top_level_spec.md) §7).
3. **Import** — UI entry TBD (toolbar on `/` vs separate route); **no placeholder** buttons for future Spotify/API features until implemented ([`top_level_spec.md`](./top_level_spec.md) Phase 2).

## 11. Deliberately out of scope (v1 UI)

1. **Audio preview** — No player controls until API and licensing/product decisions exist.
2. **Placeholder** “coming soon” provider buttons — None for now.
3. **Modal-based match review** — Replaced by **secondary docked panel** (modals only for small confirm dialogs if needed).
4. **Mobile-first** layout — **Desktop-first**; tablet/narrow degradation acceptable later.

## 12. API dependencies (stub)

| UI area | Likely endpoints (to refine in `apps/api`) |
| ------- | --------------------------------------------- |
| Main table | `GET` tracks with query params for tab/filter |
| Secondary panel | `GET` match candidates for `track_id` |
| Decisions | `POST` confirm / pick / reject |
| Imports | `POST` multipart TSV/CSV |
| User prefs | `GET/PATCH` settings (or local-only for theme/density initially) |

## 13. Document map

| Doc | Role |
| --- | ---- |
| [`design-system.md`](./design-system.md) | Tokens, Tailwind, Radix/shadcn, tables |
| [`data-model.md`](./data-model.md) | `source_tracks`, `library_tracks`, tabs vs queries |
| [`top_level_spec.md`](./top_level_spec.md) | Matching semantics, snapshots |
| [`tech-approach.md`](./tech-approach.md) | Stack, Docker, Firebase |
