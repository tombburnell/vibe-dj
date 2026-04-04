# Music Collection Automation

Automate downloading tracks for your DJ collection by comparing Spotify playlists with your rekordbox collection and generating Amazon Music purchase links for missing tracks.

## Documentation

1. **[Product spec](docs/top_level_spec.md)** — current direction (web app, hosting, matching, snapshots).
2. **[UI spec](docs/UI.md)** — layout, routes, primary/secondary tables, auth guard.
3. **[Design system](docs/design-system.md)** — DJ-style dark/light themes, density, Tailwind, Radix/shadcn.
4. **[Data model](docs/data-model.md)** — Postgres: `source_tracks`, `library_tracks`, playlists, links.
5. **[Technical approach](docs/tech-approach.md)** — React (Vite) + TypeScript frontend, Python API, Docker, Postgres.
6. **[Archived requirements](docs/old/old_reqs.md)** — detailed CLI-era functional spec and acceptance criteria.
7. **[Legacy implementation](docs/old/tech-approach.md)** — archived SQLite / `mm` CLI era detail.

**Apps:** `apps/api` (FastAPI, `uv sync`) · `apps/web-frontend` (Vite, `npm install && npm run dev` — proxies `/api` to port 8000).

**Docker (Postgres + API + Vite, file watch reload):** from repo root run `docker compose -f docker-compose.local.yml up`. UI at http://localhost:5173, API at http://localhost:8000. DB URL: `postgresql+psycopg://trackmapper:trackmapper@localhost:5432/trackmapper`. Optional wrapped copy URL: set `SPECIAL_LINK_PREFIX` in `apps/web-frontend/.env` (see `apps/web-frontend/README.md`). With Docker Compose, do not pass an empty `SPECIAL_LINK_PREFIX` into the `web` service or it overrides that file.

## Features

- **Extract Spotify playlists** - No developer account needed! Works with public playlist URLs
- **Parse rekordbox collections** - Supports both XML exports and database files
- **Fuzzy track matching** - Handles variations in artist/title names
- **Amazon Music integration** - Automatically generates purchase links for missing tracks
- **Comprehensive reports** - Generates detailed reports of missing tracks with links

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Spotify playlist URL (public playlists work without API credentials)
- rekordbox collection file (XML export or database file)

## Installation

1. Clone or navigate to the project directory:
```bash
cd music
```

2. Install dependencies using uv:
```bash
uv sync
```

This will create a virtual environment and install all required packages.

## Usage

### Basic Usage

Compare a Spotify playlist with your rekordbox collection:

```bash
uv run python src/download_tracks.py \
  "https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH" \
  --rekordbox-xml path/to/rekordbox_export.xml
```

### Using rekordbox Database

If you have access to the rekordbox database file:

```bash
uv run python src/download_tracks.py \
  "https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH" \
  --rekordbox-db path/to/rekordbox.db
```

### Advanced Options

```bash
uv run python src/download_tracks.py \
  "https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH" \
  --rekordbox-xml rekordbox.xml \
  --output-dir ./reports \
  --match-threshold 90.0 \
  --export-json \
  --skip-amazon
```

**Options:**
- `--rekordbox-xml` - Path to rekordbox XML export file
- `--rekordbox-db` - Path to rekordbox database file (optional)
- `--output-dir` - Output directory for reports (default: `./output`)
- `--match-threshold` - Fuzzy match threshold 0-100 (default: 85.0)
- `--skip-amazon` - Skip Amazon Music search (faster)
- `--export-json` - Export intermediate JSON files

## Getting Your rekordbox Collection

### Option 1: Export XML from rekordbox

1. Open rekordbox
2. Go to **File** → **Export** → **Export Collection in xml format**
3. Save the XML file
4. Use `--rekordbox-xml` with the path to this file

### Option 2: Use Database File

If you have access to the rekordbox database file (usually located in rekordbox's data directory), you can use it directly with `--rekordbox-db`.

## Output Files

The script generates the following files in the output directory:

- **missing_tracks.txt** - List of tracks missing from your rekordbox collection
- **amazon_links.txt** - Amazon Music purchase links for missing tracks (if not using `--skip-amazon`)
- **spotify_tracks.json** - Exported Spotify playlist data (if using `--export-json`)
- **rekordbox_tracks.json** - Exported rekordbox collection data (if using `--export-json`)

## Example Workflow

1. **Find a Spotify playlist** you want to add to your collection
   ```
   https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH
   ```

2. **Export your rekordbox collection** as XML

3. **Run the comparison**:
   ```bash
   uv run python src/download_tracks.py \
     "https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH" \
     --rekordbox-xml ~/Desktop/rekordbox_export.xml
   ```

4. **Review the reports** in the `output/` directory:
   - Check `missing_tracks.txt` for tracks you don't have
   - Use `amazon_links.txt` to purchase/download missing tracks

5. **Manually review** before purchasing to avoid duplicates

## Individual Scripts

You can also use the individual modules:

### Extract Spotify Playlist

```bash
uv run python src/spotify_client.py "https://open.spotify.com/playlist/3jHidbU049dUQ5mIOx20jH"
```

### Parse rekordbox Collection

```bash
uv run python src/rekordbox_parser.py path/to/rekordbox.xml
```

### Match Tracks

```bash
uv run python src/track_matcher.py spotify_tracks.json rekordbox_tracks.json
```

### Search Amazon Music

```bash
uv run python src/amazon_music.py
```

## Troubleshooting

### Spotify Playlist Extraction Fails

- Ensure the playlist URL is public
- Try using just the playlist ID instead of full URL
- Check your internet connection

### rekordbox Parsing Issues

- Verify the XML file is a valid rekordbox export
- Try exporting again from rekordbox if parsing fails
- For database files, ensure you have read permissions

### Amazon Music Search Not Working

- Amazon's website structure may change, breaking the scraper
- Use `--skip-amazon` to skip this step and manually search
- The missing_tracks.txt file contains all the information you need

### Match Threshold Too High/Low

- Lower threshold (e.g., 75.0) for more matches (may include false positives)
- Higher threshold (e.g., 95.0) for stricter matching (may miss some matches)
- Default 85.0 is usually a good balance

## Project Structure

```
music/
├── src/
│   ├── spotify_client.py      # Spotify playlist extraction
│   ├── rekordbox_parser.py     # rekordbox collection parsing
│   ├── track_matcher.py        # Track comparison logic
│   ├── amazon_music.py         # Amazon Music search
│   └── download_tracks.py     # Main orchestration script
├── pyproject.toml              # Project configuration
├── env.example                 # Environment variables template
└── README.md                   # This file
```

## Dependencies

- `spotifyscraper` - Extract Spotify playlist data without API
- `pyrekordbox` - Parse rekordbox databases and XML files
- `rapidfuzz` - Fast fuzzy string matching
- `requests` - HTTP library
- `beautifulsoup4` - HTML parsing for Amazon Music

## Limitations

- **Public playlists only** - Private Spotify playlists require API access
- **Amazon scraping** - May break if Amazon changes their website structure
- **Manual review recommended** - Always review missing tracks before purchasing

## Contributing

This is a personal automation tool, but feel free to adapt it for your needs!

## License

MIT

