# ⚠️ DEPRECATED

This specification has been merged into [`tech-approach.md`](./tech-approach.md).

Please refer to `tech-approach.md` for current technical documentation.

---

# Track Database System Specification (DEPRECATED)

## Overview

> **This document is deprecated and kept for historical reference only.**
>
> All technical specifications have been consolidated into [`tech-approach.md`](./tech-approach.md), which reflects the current SQLite-based architecture with unified `LibraryTrack` entities.

A simple JSON-based database system for managing DJ music collection tracks, tracking their sources (Spotify playlists), download status, Rekordbox collection status, and Amazon Music purchase links.

## Database Structure

### JSON File Format

The database is stored as a single JSON file (`music_db.json`) with the following structure:

```json
{
  "tracks": [
    {
      "title": "Track Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "duration_ms": 240000,
      "spotify_id": "track_id",
      "spotify_url": "https://open.spotify.com/track/...",
      "playlists": ["Playlist Name"],
      "amazon_url": "https://music.amazon.com/...",
      "amazon_search_url": "https://www.amazon.com/s?k=...",
      "amazon_price": "$0.99",
      "amazon_last_searched": "2026-01-20T15:40:51.905467",
      "in_rekordbox": false,
      "rekordbox_file_path": null,
      "downloaded": false,
      "download_path": null,
      "download_date": null,
      "last_updated": "2026-01-20T15:40:51.905488",
      "id": "spotify_track_id"
    }
  ],
  "metadata": {
    "version": "1.0",
    "last_updated": "2026-01-20T15:40:51.905488",
    "playlists": {
      "Playlist Name": {
        "name": "Playlist Name",
        "source": "chosic.com",
        "csv_file": "playlists/koko-groove.csv",
        "last_imported": "2026-01-20T15:40:51.905488"
      }
    }
  }
}
```

### Track Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Track title (required) |
| `artist` | string | Artist name (required) |
| `album` | string \| null | Album name (optional) |
| `duration_ms` | integer \| null | Track duration in milliseconds (optional) |
| `spotify_id` | string \| null | Spotify track ID (optional) |
| `spotify_url` | string \| null | Spotify track URL (optional) |
| `playlists` | array[string] | List of playlist names this track belongs to |
| `amazon_url` | string \| null | Direct Amazon Music product URL (preferred: track/album, fallback: artist page) |
| `amazon_search_url` | string \| null | Amazon search URL (generated, always available) |
| `amazon_price` | string \| null | Price from Amazon (if found) |
| `amazon_last_searched` | string \| null | ISO timestamp of last Amazon search attempt |
| `in_rekordbox` | boolean | Whether track exists in Rekordbox collection |
| `rekordbox_file_path` | string \| null | File path in Rekordbox collection |
| `downloaded` | boolean | Whether track has been downloaded |
| `download_path` | string \| null | File system path where track is stored |
| `download_date` | string \| null | ISO timestamp when track was marked as downloaded |
| `last_updated` | string | ISO timestamp of last update |
| `id` | string | Unique track identifier (generated: `spotify_{spotify_id}` or MD5 hash) |

## Operations

### 1. Add Tracks from Spotify Playlist (CSV)

**Command:** `add-playlist`

**Input:** CSV file exported from chosic.com or similar Spotify playlist export tool

**CSV Format Expected:**
- Columns: `Song`, `Artist`, `Album`, `Duration`, `Spotify Track Id`
- Duration format: `MM:SS` (converted to milliseconds)

**Behavior:**
- Parse CSV file and extract track metadata
- For each track:
  - Check if track already exists in database (by Spotify ID or fuzzy matching)
  - If exists: merge playlists, update metadata
  - If new: add to database
- Register playlist in metadata
- Save database

**Deduplication:**
- Exact match by Spotify ID (if available)
- Fuzzy matching on artist + title (threshold: 85% similarity)
- Merges playlists when duplicates found

### 2. Update Tracks from Rekordbox Collection

**Command:** `update-rekordbox`

**Input:** Rekordbox XML export file

**Behavior:**
- Parse Rekordbox XML export
- For each Rekordbox track:
  - Find matching track in database (fuzzy matching on artist + title)
  - Update database track:
    - Set `in_rekordbox = true`
    - Set `rekordbox_file_path` to file path from Rekordbox
- Save database

**Matching:**
- Uses fuzzy string matching (rapidfuzz) with threshold: 85%
- Compares normalized artist + title strings
- Handles variations in formatting, punctuation, etc.

### 3. Fetch Amazon Links for Tracks Without Links

**Command:** `fetch-amazon-links`

**Options:**
- `--missing-only`: Only fetch links for tracks not downloaded and not in Rekordbox
- `--spotify-id <id>`: Fetch link for specific track by Spotify ID
- `--track-id <id>`: Fetch link for specific track by database ID
- `--force`: Force re-fetch even if `amazon_url` already exists

**Behavior:**
- Find tracks that need Amazon links (no `amazon_url`)
- For each track:
  - Search Amazon Music via DuckDuckGo (bypasses bot detection)
  - Prioritize track/album URLs over artist pages
  - Query prioritization: track name first, then artist
  - Filter out artist pages if track/album results found
  - If results found:
    - Update database with `amazon_url`, `amazon_search_url`, `amazon_price`
    - Update `amazon_last_searched` timestamp
  - If no results found:
    - Do NOT update database (only update on successful finds)
- Rate limiting: 2 second delay between requests
- Save database periodically (every 10 tracks)

**Search Strategy:**
1. Try DuckDuckGo search with multiple query patterns:
   - `site:music.amazon.com "{title}" "{artist}"` (track prioritized)
   - `site:music.amazon.com "{title}"` (track only)
   - `site:music.amazon.com "{artist}" "{title}"` (original order)
   - `site:amazon.com "{title}" "{artist}" digital music` (fallback)
2. Filter results:
   - Prefer track/album URLs (not `/artists/` pages)
   - Return artist pages only if no track/album results found
3. Fallback to direct Amazon scraping if DuckDuckGo fails

### 4. Fetch Amazon Links for Missing Tracks

**Command:** `fetch-amazon-links --missing-only`

**Behavior:**
- Same as Operation 3, but only processes tracks where:
  - `downloaded = false` AND
  - `in_rekordbox = false`
- Useful for finding purchase links only for tracks you don't have yet

### 5. Mark Tracks as Downloaded from File Listing

**Command:** `scan-downloads`

**Input:** Directory path to scan for music files

**Behavior:**
- Scan directory recursively for music files (common extensions: `.mp3`, `.flac`, `.m4a`, `.wav`, etc.)
- For each file found:
  - Extract metadata (title, artist, album) from file tags
  - Find matching track in database (fuzzy matching)
  - Update database track:
    - Set `downloaded = true`
    - Set `download_path` to file path
    - Set `download_date` to current timestamp
- Save database

**Matching:**
- Uses fuzzy string matching on artist + title
- Handles variations in file naming vs. database entries

## Query Operations

### Get Tracks Without Amazon Links

Returns all tracks where `amazon_url` is null.

### Get Missing Tracks

Returns all tracks where:
- `downloaded = false` AND
- `in_rekordbox = false`

Useful for generating reports of tracks that need to be purchased/downloaded.

## Design Principles

1. **Simple JSON Storage**: Single file, human-readable, easy to backup
2. **Deduplication**: Automatic merging of duplicate tracks from multiple playlists
3. **Fuzzy Matching**: Handles variations in track metadata across sources
4. **Non-Destructive Updates**: Only updates fields that are missing or need updating
5. **Graceful Degradation**: Falls back to search URLs if direct product links unavailable
6. **Rate Limiting**: Built-in delays to avoid overwhelming external services
7. **Backup on Save**: Automatic backups created before database saves

## File Structure

```
music/
├── music_db.json              # Main database file
├── playlists/
│   └── *.csv                  # Spotify playlist CSV exports
├── src/
│   ├── track_db.py           # Database management & CLI
│   ├── spotify_client.py      # CSV playlist parser
│   ├── rekordbox_parser.py    # Rekordbox XML parser
│   ├── rekordbox_updater.py   # Rekordbox update operation
│   ├── amazon_music.py        # Amazon Music search
│   ├── download_scanner.py    # File system scanner
│   └── track_matcher.py        # Fuzzy matching utilities
└── docs/
    └── spec.md                # This specification
```

## Usage Examples

### Add a playlist from CSV
```bash
uv run python -m src.track_db add-playlist playlists/koko-groove.csv --name "Koko Groove"
```

### Update from Rekordbox XML export
```bash
uv run python -m src.track_db update-rekordbox rekordbox/collection.xml
```

### Fetch Amazon links for all tracks without links
```bash
uv run python -m src.track_db fetch-amazon-links
```

### Fetch Amazon links for missing tracks only
```bash
uv run python -m src.track_db fetch-amazon-links --missing-only
```

### Fetch Amazon link for specific track
```bash
uv run python -m src.track_db fetch-amazon-links --spotify-id 0sQDaCCZDNsdSBnP66Z8BN
```

### Scan downloads directory
```bash
uv run python -m src.track_db scan-downloads /path/to/music/files
```

## Future Enhancements

- Parse artist pages to find specific tracks when only artist page found
- Support for other music sources (Bandcamp, Beatport, etc.)
- Export reports in various formats (CSV, HTML)
- Web UI for browsing and managing tracks
- Automatic playlist re-sync from Spotify (when API access available)
