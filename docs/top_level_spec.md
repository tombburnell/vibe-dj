# Track Mapper — Top-Level Product Spec

> High-level requirements for the DJ “wishlist vs library” product: find tracks you want but do not yet own or import, with robust matching and a web UI. Detailed CLI-era use cases and acceptance criteria are archived in [`old/old_reqs.md`](./old/old_reqs.md). Current engineering approach is in [`tech-approach.md`](./tech-approach.md); legacy SQLite/CLI implementation detail is in [`old/tech-approach.md`](./old/tech-approach.md). **UX:** [`UI.md`](./UI.md) (screens, layout, routes); [`design-system.md`](./design-system.md) (visual system, Tailwind, Radix/shadcn).

## 1. Problem & outcome

1. **Problem:** DJs maintain desired tracks (e.g. from playlists) and a local music **library** (Rekordbox, Traktor, etc.). Names and metadata differ, so simple string compare misses real matches and creates false gaps.
2. **Outcome:** A **web application** (multi-user, hosted) that shows filterable track lists, surfaces **missing** items with **purchase/download links**, and supports **human-in-the-loop** matching decisions that **persist** across automated rematches.
3. **Deprecated:** The existing Python CLI (`mm`, etc.) is **deprecated**; a **new** CLI may appear later, after the web tool. Until then, docs and contributors should treat the web app + API as the primary product surface.

## 2. Personas & audience

1. **Primary:** DJs like the author—manage large libraries and playlist-driven wishlists.
2. **Deployment:** Same codebase should be **hostable for arbitrary users** (not only local clone), with **per-user data isolation**.

## 3. Authentication & tenancy

1. **Authentication:** **Firebase Authentication** (email/social as configured); every domain record is associated with a **`user_id`**.
2. **Data:** No shared global `music.db` across users; storage and APIs are scoped by authenticated user.

## 4. Glossary (UI-oriented)

1. **In library** — Track exists in the DJ app catalog import (e.g. Rekordbox **TSV** export today; other tools later). Represents “already in collection” from the app’s perspective.
2. **Downloaded** — File acquired and tracked as on disk, **not yet** reflected in **In library** (user will import later).
3. **Wishlist / desired** — In the data model, primarily **`source_tracks.on_wishlist`** (internal filter), which may include tracks from **playlists**, **manual** adds, or other **`source_kind`** values—see [`data-model.md`](./data-model.md). Naming in the UI can be “Wishlist” or “Desired”; avoid a vague-only label “have.”
4. **Missing (derived)** — Wishlist items that are **not** In library and **not** Downloaded (default focus); UI may offer a **toggle** to show wishlist rows that are already owned.

## 5. Phasing

### Phase 1 (ship first)

1. **Wishlist source:** Same as today—**Spotify playlist data** the project already ingests (e.g. CSV-style lists); no requirement to add new providers before the core UI and matching work.
2. **Library import:** **Rekordbox TSV** only—this is what the current `mm` / SQLite path implements; do not expand to XML/DB until explicitly prioritized.
3. **Purchase links:** **Pluggable** list of providers; **Amazon first**. **Cache URLs indefinitely** for now; link rot and refresh policy are deferred.
4. **Client:** **Web** — **React** + **Vite** + **Tailwind** + TypeScript SPA (dense tables, docked **secondary panel** for match review—see [`UI.md`](./UI.md)). **Mobile/native** clients are out of scope until revisited.

### Phase 2 (after interface stabilizes)

1. Additional wishlist sources (e.g. Apple Music, YouTube, Beatport carts, plain imports).
2. **Spotify Web API** (or equivalent) where credentials allow.
3. Extra purchase providers (Beatport, Bandcamp, Juno, …).
4. Optional **new** CLI aligned with the same API as the web app.

## 6. Core capabilities

1. **Import wishlist** — User uploads or connects sources (Phase 1: existing Spotify list flow); dedupe across playlists where applicable.
2. **Import library snapshot** — User uploads a **library export** (Phase 1: Rekordbox TSV). Each import creates a new **`library_snapshot_id`** (monotonic or otherwise totally ordered per user).
3. **Match** — Heuristic matcher (existing token/score pipeline) proposes links between wishlist rows and library rows; optional **LLM** assist only on **borderline** cases using **small candidate sets**, not full-catalog prompts (see §8).
4. **Review UI** — Primary table with filters/tabs (library / downloaded / wishlist / missing); **docked secondary table/panel** for match candidates when a row is selected (**not** a blocking modal for core review—see [`UI.md`](./UI.md)). Actions: **confirm**, **pick another candidate**, **reject**.
5. **Purchase resolver** — For missing (or user-requested) rows, resolve and store links from configured providers (Amazon first).
6. **Persistence of human decisions** — User actions are **durable**; automated rematch must not undo them silently (see §7).

## 7. Matching decisions, snapshots, and “no match”

### 7.1 Decision types (conceptual)

1. **Confirm** — User accepts the proposed library row (or best auto match).
2. **Pick alternative** — User selects another row from the **secondary panel** listing **top-K** heuristic candidates (same K the server would send to an LLM).
3. **Reject (no match)** — User asserts **no row in the library catalog matches** this wishlist track.

### 7.2 Library snapshots

1. Each **library import** receives a **`library_snapshot_id`** (new id per import).
2. Matcher may use the **full catalog** across snapshots or restrict candidates by policy; either way, **user decisions override** auto logic.

### 7.3 Reject semantics (agreed rule)

1. **Reject** means: **no match for this wishlist track against the library for all `library_snapshot_id` values from the first import through and including the snapshot active at reject time** (i.e. the entire known library history up to “now” when the user rejected).
2. After a **later** import adds a **new** `library_snapshot_id`, the system **may** propose new candidates involving rows that first appeared in that **new** snapshot (or that were never considered under the prior rejection scope), because they were not part of “library up to and including” the snapshot at reject time.
3. The system **must not** “resurrect” a **user-rejected** pairing (same wishlist identity + same library row identity) **without explicit user action** (e.g. user opens review and confirms a previously rejected candidate).

### 7.4 Rematch behavior

1. **Confirmed** or **user-picked** links: do **not** auto-overwrite on rematch; allow optional explicit “re-run match” with warning.
2. **Rejected:** do not auto-attach low-confidence guesses; surface **new candidates** only when policy allows (e.g. new snapshot rows).
3. **No user decision + borderline score:** eligible for review queue and/or batch LLM assist.

## 8. LLM assist (optional, non–whole-catalog)

1. **Primary** matching remains **heuristics** (inverted index, normalization, scoring).
2. **LLM** runs on **batches** of wishlist tracks in a **middle confidence band**, with **only top-K candidates** per track in context—never the full 20k+ library in one prompt.
3. If more catalog context is needed, use **tools** (e.g. `search_library(query, limit)`) backed by SQLite **FTS**, trigram, or the existing index—not raw full exports.
4. Manual **ChatGPT** workflows documented in [`chatgpt_matching_prompt.md`](./chatgpt_matching_prompt.md) remain a reference; the product target is **server-side** or **job-based** integration when implemented.

## 9. Deployment & packaging

1. **Target:** Single **Docker** image (or one compose stack) that runs the **web frontend + API + whatever worker** is needed, suitable for **Fly.io** or a **Hetzner VM** (or similar).
2. **Constraint:** Prefer **one deployable unit** for small-team operations; scale-out and managed queues are optional later.
3. **Stack:** **Python** backend (API, matching, DB, Rekordbox/audio/ML-friendly ecosystem) and **React + Vite** frontend (TypeScript). Single Docker image; details in [`tech-approach.md`](./tech-approach.md).

## 10. Non-goals (current)

1. Rekordbox / Traktor **write-back** (library remains read-only import).
2. **Guaranteed** correctness without user review for purchases.
3. **Native** Flutter or mobile-first clients (revisit after web).

## 11. Traceability

| Topic | Where to look |
| ----- | ------------- |
| Archived detailed use cases & AC | [`old/old_reqs.md`](./old/old_reqs.md) |
| Current engineering (React/Vite, Python API, Docker, Postgres) | [`tech-approach.md`](./tech-approach.md) |
| Legacy DB schema, indexes, normalization, `mm` CLI | [`old/tech-approach.md`](./old/tech-approach.md) |
| Manual LLM prompt / JSON workflow | [`chatgpt_matching_prompt.md`](./chatgpt_matching_prompt.md) |
| UI layout, routes, panels, filters | [`UI.md`](./UI.md) |
| Design tokens, themes, tables, Radix/shadcn | [`design-system.md`](./design-system.md) |
| Database tables, playlists, links | [`data-model.md`](./data-model.md) |
