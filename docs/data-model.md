# Track Mapper — Data Model

> Postgres-oriented schema for the multi-user web app. Product rules (snapshots, reject semantics, glossary) live in [`top_level_spec.md`](./top_level_spec.md). Legacy single-table **`LibraryTrack`** / `tracks` in SQLite is documented in [`old/tech-approach.md`](./old/tech-approach.md)—that model **merged** wishlist + library + match into one row; **this** model **normalizes** those concerns.

## 1. Design principles

1. **`user_id`** (Firebase UID) on every tenant-scoped table; enforce in API and DB (RLS optional later).
2. **Library catalog** rows live in **`library_tracks`** tied to a **`library_snapshot`** (one import = one snapshot).
3. **Non-library** material (Spotify CSV, manual adds, future sources) lives in **`source_tracks`**. The name is intentionally broad; use **`source_kind`** (or similar) to subcategorize.
4. **Spotify identity** stays on **`source_tracks`** when known. **Do not require `spotify_id` on `library_tracks`**. Provenance to Spotify flows through **`source_library_links`** (and optional denormalized display fields on API DTOs only).
5. **Playlists** are a separate entity; **many-to-many** with `source_tracks` so the **same track can appear in multiple playlists**.
6. **Wishlist** is an **internal product flag** on `source_tracks` (`on_wishlist`), not the same thing as “appears in a playlist.” Users can manually add sources, tag wishlist independently, or import from playlists.
7. **Downloaded (not yet in library)** — **`local_file_path`** + timestamps on `source_tracks` (see §3.3). Add a separate **`source_track_files`** table later if multiple local files per logical source row are needed.

## 2. Entity overview

```text
users (optional profile; or implicit via Firebase only)
  │
  ├── library_snapshots
  │     └── library_tracks
  │
  ├── playlists
  │     └── source_track_playlists ─── source_tracks
  │
  └── source_tracks
          └── source_library_links ───► library_tracks
```

## 3. Tables (logical schema)

### 3.1 `library_snapshots`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | UUID PK | |
| `user_id` | TEXT NOT NULL | Firebase UID |
| `imported_at` | TIMESTAMPTZ NOT NULL | |
| `label` | TEXT NULL | User-visible name, e.g. file name or “Dec 2025 export” |
| `source_filename` | TEXT NULL | Original upload name |
| `content_hash` | TEXT NULL | Dedup / “same file re-uploaded” detection |

**Ordering:** `imported_at` (or monotonic `id`) defines snapshot order for [`top_level_spec.md`](./top_level_spec.md) §7.3 **reject-through-snapshot** semantics.

### 3.2 `library_tracks`

One row per line in a Rekordbox (or other) **library export** for a given snapshot.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | UUID PK | |
| `user_id` | TEXT NOT NULL | Denormalized for simpler RLS/queries |
| `library_snapshot_id` | UUID FK NOT NULL | → `library_snapshots.id` |
| `title` | TEXT NOT NULL | |
| `artist` | TEXT NOT NULL | |
| `album` | TEXT NULL | |
| `duration_ms` | INT NULL | |
| `file_path` | TEXT NOT NULL | As in export (DJ app path) |
| `bpm` | REAL NULL | |
| `musical_key` | TEXT NULL | |
| `genre` | TEXT NULL | |
| `tags` | JSONB NULL | **v2+** — evolving DJ/library fields |
| `created_at` | TIMESTAMPTZ | |

**No `spotify_id` here by default.** If a future feature needs denormalized Spotify id on library rows, add it as an **optional** column after explicit product approval (risk: duplicates, wrong merges).

**Indexes (suggested):** `(user_id, library_snapshot_id)`; `(user_id, library_snapshot_id, file_path)` unique optional if export guarantees unique paths per snapshot.

### 3.3 `source_tracks`

Things the user tracks **outside** the current library import: playlist lines, manual entries, future Beatport rows, etc.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | UUID PK | |
| `user_id` | TEXT NOT NULL | |
| `source_kind` | TEXT NOT NULL | e.g. `playlist_csv`, `manual`, `beatport` (enum in app) |
| `title` | TEXT NOT NULL | |
| `artist` | TEXT NOT NULL | |
| `album` | TEXT NULL | |
| `duration_ms` | INT NULL | |
| `spotify_id` | TEXT NULL | |
| `spotify_url` | TEXT NULL | |
| `on_wishlist` | BOOLEAN NOT NULL DEFAULT true | **Internal filter** — “show in wishlist / missing workflow”; importers may set **false** for `source_kind` values that are reference-only |
| `local_file_path` | TEXT NULL | **Downloaded** file on disk (not yet in Rekordbox) |
| `downloaded_at` | TIMESTAMPTZ NULL | |
| `amazon_url` | TEXT NULL | Pluggable providers later — see product spec |
| `amazon_search_url` | TEXT NULL | |
| `amazon_price` | TEXT NULL | |
| `amazon_link_title` | TEXT NULL | Display line for the **best** Amazon result (from search metadata). |
| `amazon_link_match_score` | REAL NULL | Searcher fuzzy score for the best result (same 0–100 scale as `amazon_candidates_json`). |
| `amazon_last_searched_at` | TIMESTAMPTZ NULL | Set when an Amazon **link search** run finished for this row (hit or miss). |
| `amazon_candidates_json` | JSONB NULL | Alternate purchase links from the last search: array of `{ url, title?, artist?, match_score?, price? }`. Best URL stays in `amazon_url`. |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**Amazon link search (Find links API):**

1. **Eligibility (UI “Need” queue)** — user has **rejected** library match for the current snapshot scope (`source_library_links.decision = rejected` per [`top_level_spec.md`](./top_level_spec.md) §7).
2. **Skip re-search** — If `amazon_last_searched_at` IS NOT NULL, the job **does not** call external search again unless the client sends **`force: true`** (re-search selected / refresh).
3. **No URL found** — Still set `amazon_last_searched_at` (and usually empty `amazon_candidates_json`) so repeated batch runs do not hammer providers.

**Semantics:**

1. **Missing (derived)** — `on_wishlist = true` AND no **confirmed** `source_library_links` row AND `local_file_path` IS NULL (exact rules in API; align with UI tabs).
2. **Downloaded** — `local_file_path` set; may still be `on_wishlist` until user clears it or links to library.

### 3.4 `playlists`

Imported or user-defined **containers** (e.g. “Koko Groove CSV import”).

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | UUID PK | |
| `user_id` | TEXT NOT NULL | |
| `name` | TEXT NOT NULL | |
| `import_source` | TEXT NULL | e.g. `chosic_csv`, `manual` |
| `created_at` | TIMESTAMPTZ | |

### 3.5 `source_track_playlists`

**Many-to-many:** same `source_track` in multiple playlists.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `source_track_id` | UUID FK | → `source_tracks.id` |
| `playlist_id` | UUID FK | → `playlists.id` |
| PK | `(source_track_id, playlist_id)` | |

**Alternative (not recommended at scale):** JSON array of playlist ids on `source_tracks` — harder to query and index.

### 3.6 `source_library_links`

Links a **source** row to at most one **chosen** library row per policy, plus **match metadata and user decisions**. Candidate lists for the UI can be **computed** (matcher output) or stored in a separate **`match_candidates`** table later.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | UUID PK | |
| `user_id` | TEXT NOT NULL | |
| `source_track_id` | UUID FK NOT NULL | |
| `library_track_id` | UUID FK NULL | Null if user **rejected** “no match” |
| `library_snapshot_id` | UUID FK NOT NULL | Snapshot the match refers to (usually **current** catalog) |
| `confidence` | REAL NULL | Last automated score 0.0–1.0 |
| `decision` | TEXT NOT NULL | e.g. `auto`, `confirmed`, `rejected`, `picked` |
| `rejected_through_snapshot_id` | UUID FK NULL | Set when `decision = rejected` — max snapshot id covered (see product spec §7.3) |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**Rules (align with [`top_level_spec.md`](./top_level_spec.md) §7):**

1. **Confirmed** / **picked** — `library_track_id` set; durable; rematcher must not overwrite silently.
2. **Rejected** — `library_track_id` null; `rejected_through_snapshot_id` records scope; new library snapshots may allow **new** proposals.

**Uniqueness:** One **active** link row per `source_track_id` + policy, or use partial unique index on `(source_track_id)` where `decision != 'superseded'` — implementation choice.

## 4. API / UI DTOs (stable contract)

1. The **database** stays normalized; **list endpoints** return **flattened** objects for the primary grid (source fields + link summary + playlist names array).
2. **Secondary panel** — `GET …/source_tracks/:id/candidates` returns `library_track`-shaped rows + scores (from matcher, snapshot-scoped).

## 5. Relationship to legacy `LibraryTrack`

| Legacy (`LibraryTrack` / single `tracks` row) | New model |
| --------------------------------------------- | -------- |
| Spotify + playlist info | `source_tracks` + `playlists` + junction |
| Rekordbox path, bpm, key | `library_tracks` |
| `in_rekordbox`, confidence | `source_library_links` |
| Amazon fields | `source_tracks` (purchase is about acquiring the **source** intent) |
| `downloaded`, `download_path` | `source_tracks.local_file_path`, `downloaded_at` |

## 6. Future extensions

1. **`source_track_files`** — multiple downloads per source row.
2. **`match_candidates`** — persist top-K per run for audit/replay.
3. **`user_saved_views`** — serialized filters for [`UI.md`](./UI.md) saved views.
4. **Additional purchase providers** — new nullable columns or `purchase_offers` child table.

## 7. Document map

| Doc | Role |
| --- | ---- |
| [`top_level_spec.md`](./top_level_spec.md) | Reject semantics, glossary |
| [`tech-approach.md`](./tech-approach.md) | Postgres, Python API |
| [`UI.md`](./UI.md) | Tabs derived from this model |
