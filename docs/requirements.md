q# Music Collection Automation — Functional Requirements

> Inputs derived from user requirements and implementation discussions. This specification focuses on user requirements and deliverables for MVP. Implementation details are documented separately in [`spec.md`](./spec.md).

## High-Level Need & Rationale

### Problem Statement

As a DJ, I need to:
1. **Discover new music** using Spotify's search and playlist features
2. **Identify missing tracks** by comparing Spotify playlists against my existing Rekordbox collection
3. **Purchase missing tracks** efficiently by finding direct Amazon Music download links
4. **Organize and improve** my Rekordbox library through duplicate detection and auto-tagging

### Current Workflow Pain Points

- **Manual comparison**: Comparing Spotify playlists with Rekordbox collection is time-consuming and error-prone
- **Metadata inconsistencies**: Rekordbox metadata is often messy (artist/title swaps, formatting variations), making manual matching difficult
- **Purchase link finding**: Manually searching Amazon for each missing track is tedious
- **Collection management**: No systematic way to identify duplicates or apply consistent tagging across tracks

### Solution Overview

This system automates the workflow of:
1. Importing Spotify playlists into a centralized track database
2. Intelligently matching playlist tracks against Rekordbox collection using hybrid matching (deterministic + LLM assistance)
3. Automatically finding Amazon Music purchase links for missing tracks
4. Tracking download status and collection status for all tracks

**Future enhancements** will enable:
- Duplicate detection within the database
- Auto-tagging based on track qualities (BPM, key, genre)
- Updating Rekordbox collection with improved metadata and tags

### Value Proposition

- **Time savings**: Automates hours of manual comparison and link-finding work
- **Accuracy**: Handles metadata inconsistencies that humans might miss
- **Completeness**: Ensures no tracks are missed during comparison
- **Organization**: Provides foundation for future collection management features

## Definitions & Scope

- **Track Database**: Centralized SQLite database (`music.db`) containing all tracks from Spotify playlists, with metadata, download status, Rekordbox collection status, and purchase links. All tracks stored as unified `LibraryTrack` entities regardless of source.
- **Spotify Playlist**: Collection of tracks discovered on Spotify, exported as CSV from third-party tools (e.g., chosic.com) for import into the system.
- **Rekordbox Collection**: Existing music library managed in Rekordbox DJ software, exported as TSV file containing track metadata, file paths, BPM, key, genre, and other DJ-specific information.
- **Hybrid Matching**: Two-phase matching system combining deterministic fuzzy matching (fast, bulk) with LLM-assisted enrichment (for borderline/unmatched cases).
- **Missing Track**: Track that exists in Spotify playlists but is not present in Rekordbox collection and has not been downloaded.
- **Primary output**: Matched tracks with Rekordbox file paths, missing tracks with Amazon Music purchase links, and download status tracking.

## MVP Scope

**In Scope:**

- SQLite database for track storage (unified `LibraryTrack` entities)
- CSV playlist import from chosic.com (or similar export tools)
- Rekordbox TSV export parsing and matching
- Hybrid matching system (deterministic + LLM for borderline cases)
- Amazon Music link finding via DuckDuckGo search
- Download directory scanning and status tracking
- Track deduplication across multiple playlists
- Confidence scoring for matches (0.0-1.0)
- Missing tracks reporting with Amazon links

**Out of Scope of MVP**

- Direct Spotify API integration (use CSV exports)
- Duplicate detection within database (future expansion)
- Auto-tagging based on track qualities (future expansion)
- Rekordbox collection updates/write-back (future expansion)
- Multiple purchase sources (Amazon Music only for MVP)
- Real-time playlist sync from Spotify
- Web UI (CLI-only for MVP)
- Multi-user collaboration features
- Playlist management within system (read-only import)

## Use Cases

**Use Case Summary:**

- **UC1** — Add Spotify Playlist to Database
- **UC2** — Match Tracks with Rekordbox Collection
- **UC3** — Find Amazon Purchase Links
- **UC4** — Generate Missing Tracks Report
- **UC5** — Mark Tracks as Downloaded
- **UC6** — Find Duplicates (Future)
- **UC7** — Auto-tag Tracks (Future)
- **UC8** — Update Rekordbox Collection (Future)

---

### UC1 — Add Spotify Playlist to Database

**Actor**: DJ/User  
**Preconditions**: User has exported Spotify playlist as CSV from chosic.com or similar tool.  
**Trigger**: User wants to add tracks from a Spotify playlist to the track database.

**Flow**:

1. User exports playlist from Spotify using third-party tool (e.g., chosic.com):
   - Exports CSV file with columns: Song, Artist, Album, Duration, Spotify Track Id
   - Duration format: MM:SS (converted to milliseconds by system)
2. User runs import command:
   ```bash
   uv run python -m src.track_db add-playlist playlists/koko-groove.csv --name "Koko Groove"
   ```
3. System processes CSV file:
   - Parses each row and extracts track metadata
   - Converts duration from MM:SS to milliseconds
   - Generates Spotify URL from track ID
4. For each track:
   - System checks for duplicates:
     - Exact match by Spotify ID (if available)
     - Fuzzy match on artist + title (threshold: 85% similarity)
   - If duplicate found:
     - Merges playlists (adds playlist name to existing track's playlist list)
     - Updates metadata if new information is available
   - If new track:
     - Adds to database with playlist association
5. System registers playlist in metadata:
   - Stores playlist name, source (chosic.com), CSV file path, import timestamp
6. System saves database with automatic backup

**Postconditions**:

- All tracks from playlist added to database (or merged if duplicates)
- Playlist registered in metadata
- Database saved with backup created

**Business Rules**:

- At least one track must be successfully parsed from CSV
- Playlist name is required
- Duplicate tracks are merged, not duplicated
- Playlist associations are preserved (tracks can belong to multiple playlists)

**Special Cases**:

- Malformed CSV rows are skipped with warning
- Missing optional fields (album, duration) are handled gracefully
- Tracks without Spotify IDs are still added (using hash-based ID generation)

---

### UC2 — Match Tracks with Rekordbox Collection

**Actor**: DJ/User  
**Preconditions**: Track database contains Spotify playlist tracks. User has exported Rekordbox collection as TSV file.  
**Trigger**: User wants to identify which Spotify tracks already exist in Rekordbox collection.

**Flow**:

1. User exports Rekordbox collection:
   - Exports all tracks as TSV file (`all-tracks.txt`)
   - Contains: Track Title, Artist, Album, Genre, BPM, Key, Time (MM:SS), Location (file path)
2. User runs matching command:
   ```bash
   uv run python -m src.track_db match-rekordbox-hybrid rekordbox/all-tracks.txt
   ```
3. System processes Rekordbox TSV:
   - Parses TSV file and extracts track metadata
   - Normalizes track data (removes junk tokens, standardizes formatting)
   - Converts Time (MM:SS) to duration_ms
   - Builds inverted token index for fast candidate generation
4. For each Spotify track in database:
   - **Phase 1: Deterministic Matching**
     - Generates normalized search tokens (base_title, artist_tokens)
     - Queries index to find candidate matches (~100 candidates)
     - Scores each candidate:
       - Title similarity (70% weight)
       - Artist similarity (25% weight)
       - Duration hint (boost/penalty based on difference)
       - Album hint (small boost if matches)
     - Calculates confidence_v1 (0.0-1.0)
   - **Phase 2: Bucketing**
     - `confidence_v1 >= 0.7` → ACCEPT (high confidence match)
     - `0.5 <= confidence_v1 < 0.7` → BORDERLINE (needs LLM help)
     - `confidence_v1 < 0.5` → UNMATCHED (needs LLM help)
   - **Phase 3: LLM-Assisted Enrichment** (for BORDERLINE/UNMATCHED)
     - Uses Cursor AI to infer track characteristics (genres, edit likelihood)
     - Re-scores top candidates with LLM signals
     - Calculates confidence_v2
5. For each match (confidence >= 0.6):
   - Updates database track:
     - Sets `in_rekordbox = true`
     - Sets `rekordbox_file_path` to matched file path
     - Sets `rekordbox_match_confidence` to confidence score
6. System saves database

**Postconditions**:

- All matchable tracks updated with Rekordbox status
- File paths stored for matched tracks
- Confidence scores recorded for match quality assessment
- Unmatched tracks remain in database for future matching attempts

**Business Rules**:

- Only updates tracks if confidence >= 0.6 (configurable minimum)
- Only updates existing matches if new confidence is significantly higher (default: +0.1 delta)
- LLM assistance only used for borderline/unmatched cases (not all tracks)
- Matching handles metadata inconsistencies (artist/title swaps, formatting variations)

**Special Cases**:

- Tracks with swapped artist/title metadata are matched correctly
- Different edits (radio vs extended mix) are matched despite duration differences
- Tracks with missing metadata (BPM, genre) still matched using available fields

---

### UC3 — Find Amazon Purchase Links

**Actor**: System  
**Preconditions**: Track database contains tracks without Amazon purchase links.  
**Trigger**: User runs command to find Amazon links for tracks.

**Flow**:

1. User runs Amazon link finding command:
   ```bash
   uv run python -m src.track_db fetch-amazon-links [--missing-only] [--spotify-id <id>]
   ```
2. System identifies tracks needing links:
   - Filters tracks where `amazon_url` is null
   - If `--missing-only`: Only tracks not downloaded and not in Rekordbox
   - If `--spotify-id`: Only specific track
3. For each track:
   - **Search Strategy**:
     - Uses DuckDuckGo search (bypasses Amazon bot detection)
     - Queries: `site:music.amazon.com "{title}" "{artist}"` (track prioritized)
     - Falls back to general Amazon search if no music-specific results
   - **Result Filtering**:
     - Prioritizes track/album URLs over artist pages
     - Filters out artist pages if track/album results found
     - Returns artist pages only as fallback if no track/album matches
   - **Link Extraction**:
     - Extracts direct Amazon Music product URL
     - Extracts price if available in search results
     - Generates search URL as fallback (always available)
4. If Amazon link found:
   - Updates database:
     - Sets `amazon_url` to product URL
     - Sets `amazon_search_url` to search URL
     - Sets `amazon_price` if available
     - Sets `amazon_last_searched` timestamp
5. If no link found:
   - Does NOT update database (only updates on successful finds)
   - Logs failure for review
6. System applies rate limiting:
   - 2 second delay between requests to avoid blocking
   - Increases delay if multiple errors occur
7. System saves database periodically (every 10 tracks) and at end

**Postconditions**:

- Tracks with found links updated in database
- Search URLs saved even if direct links unavailable
- Timestamps recorded for tracking search attempts

**Business Rules**:

- Only updates database when actual Amazon links are found (not just search URLs)
- Prefers track/album URLs over artist pages
- Rate limiting prevents service blocking
- Failed searches don't update database (allows retry)

**Special Cases**:

- Amazon search failures (503 errors) are handled gracefully
- Search URLs generated even if direct scraping fails
- Tracks can be re-searched using `--force` flag if needed

---

### UC4 — Generate Missing Tracks Report

**Actor**: DJ/User  
**Preconditions**: Track database contains tracks with Rekordbox matching and Amazon links completed.  
**Trigger**: User wants to see which tracks need to be purchased/downloaded.

**Flow**:

1. System identifies missing tracks:
   - Queries database for tracks where:
     - `downloaded = false` AND
     - `in_rekordbox = false`
2. System generates report:
   - Lists each missing track with:
     - Artist and title
     - Album (if available)
     - Spotify URL
     - Amazon purchase link (if available)
     - Amazon price (if available)
     - Playlist associations
3. Report can be:
   - Displayed in terminal
   - Saved to file (future enhancement)
   - Exported as JSON (future enhancement)

**Postconditions**:

- User has list of tracks to purchase/download
- Amazon links available for direct purchase
- Clear visibility into what's missing from collection

**Business Rules**:

- Only includes tracks that are truly missing (not downloaded, not in Rekordbox)
- Includes Amazon links when available for easy purchase
- Groups by playlist for organization (future enhancement)

---

### UC5 — Mark Tracks as Downloaded

**Actor**: DJ/User  
**Preconditions**: User has downloaded music files to a directory. Track database contains tracks.  
**Trigger**: User wants to update database with downloaded tracks.

**Flow**:

1. User runs download scanning command:
   ```bash
   uv run python -m src.track_db scan-downloads /path/to/downloads
   ```
2. System scans directory:
   - Recursively searches for music files
   - Supported formats: `.mp3`, `.flac`, `.m4a`, `.wav`, `.aiff`, etc.
   - Extracts metadata from file tags (ID3, etc.)
3. For each file found:
   - Extracts metadata:
     - Title, Artist, Album from file tags
     - File path and modification date
   - Finds matching track in database:
     - Uses fuzzy matching on artist + title
     - Handles variations in file naming vs. database entries
4. If match found:
   - Updates database track:
     - Sets `downloaded = true`
     - Sets `download_path` to file path
     - Sets `download_date` to current timestamp
5. System saves database

**Postconditions**:

- Downloaded tracks marked in database
- File paths stored for reference
- Download dates recorded

**Business Rules**:

- Only updates tracks with confident matches (fuzzy match threshold)
- Handles files with missing or incorrect metadata tags
- Preserves existing download information if already set

**Special Cases**:

- Files without metadata tags are skipped with warning
- Multiple files matching same track are handled (updates with latest)
- Files in subdirectories are found recursively

---

### UC6 — Find Duplicates (Future)

**Actor**: DJ/User  
**Preconditions**: Track database contains tracks from multiple playlists.  
**Trigger**: User wants to identify duplicate tracks in database.

**Note**: Duplicate detection functionality is deferred to post-MVP. MVP focuses on deduplication during import.

**Flow** (Planned):

1. System analyzes all tracks in database
2. Identifies potential duplicates:
   - Same Spotify ID (exact duplicate)
   - Similar artist + title (fuzzy match)
   - Same file path (if Rekordbox paths match)
3. Generates duplicate report:
   - Lists duplicate groups
   - Shows confidence scores
   - Suggests which tracks to keep/remove
4. User reviews and merges duplicates

**Postconditions**:

- Duplicate tracks identified
- Database cleaned of duplicates
- Playlist associations preserved

---

### UC7 — Auto-tag Tracks (Future)

**Actor**: System  
**Preconditions**: Track database contains tracks with metadata. Rekordbox collection has BPM, key, genre information.  
**Trigger**: User wants to automatically tag tracks based on qualities.

**Note**: Auto-tagging functionality is deferred to post-MVP.

**Flow** (Planned):

1. System analyzes track metadata:
   - BPM ranges
   - Musical keys
   - Genres
   - Energy levels (if available)
2. Suggests tags:
   - "High Energy" (>130 BPM)
   - "Deep House" (genre-based)
   - "Minor Key" (key-based)
3. Updates database with tags
4. Tags can be used for:
   - Playlist organization
   - Rekordbox collection updates
   - Search and filtering

**Postconditions**:

- Tracks tagged with relevant qualities
- Tags available for filtering and organization

---

### UC8 — Update Rekordbox Collection (Future)

**Actor**: System  
**Preconditions**: Track database contains tracks with updated metadata, tags, or corrections.  
**Trigger**: User wants to sync database changes back to Rekordbox.

**Note**: Rekordbox write-back functionality is deferred to post-MVP. MVP is read-only for Rekordbox.

**Flow** (Planned):

1. System identifies tracks with updates:
   - Metadata corrections
   - New tags
   - Genre updates
2. Exports updates to Rekordbox-compatible format
3. Updates Rekordbox collection:
   - Modifies track metadata in Rekordbox database
   - Updates tags and custom fields
   - Preserves existing Rekordbox-specific data

**Postconditions**:

- Rekordbox collection updated with database changes
- Two-way sync between database and Rekordbox

---

## Acceptance Criteria

### P0 - Critical (Must Have)

| Ref      | Criteria                                                                                                                                    | Priority |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| **AC1**  | System accepts CSV playlist exports from chosic.com with columns: Song, Artist, Album, Duration (MM:SS), Spotify Track Id.                  | P0       |
| **AC2**  | Playlist import deduplicates tracks using Spotify ID (exact match) and fuzzy matching on artist + title (85% threshold).                  | P0       |
| **AC3**  | System parses Rekordbox TSV export with columns: Track Title, Artist, Album, Genre, BPM, Key, Time (MM:SS), Location (file path).         | P0       |
| **AC4**  | Hybrid matching system uses deterministic fuzzy matching for bulk matching (confidence >= 0.7) and LLM assistance for borderline cases.    | P0       |
| **AC5**  | Matching handles metadata inconsistencies: artist/title swaps, formatting variations, different edits (radio vs extended mix).             | P0       |
| **AC6**  | System updates database tracks with Rekordbox file paths and confidence scores (0.0-1.0) for all matches with confidence >= 0.6.          | P0       |
| **AC7**  | Amazon link finding uses DuckDuckGo search to bypass bot detection and finds direct Amazon Music product URLs.                              | P0       |
| **AC8**  | Amazon search prioritizes track/album URLs over artist pages, only returns artist pages as fallback if no track/album matches found.     | P0       |
| **AC9**  | System only updates database with Amazon links when actual product URLs are found (not just search URLs on failure).                        | P0       |
| **AC10** | Download scanning extracts metadata from music files and matches them to database tracks using fuzzy matching.                              | P0       |
| **AC11** | Database automatically creates backups before saving to prevent data loss.                                                                  | P0       |
| **AC12** | All track operations preserve existing data (non-destructive updates) and only modify specified fields.                                     | P0       |
| **AC13** | System handles errors gracefully: malformed CSV rows, missing metadata, API failures don't crash the system.                                | P0       |
| **AC14** | Rate limiting prevents service blocking (2 second delays between Amazon searches, increases on errors).                                    | P0       |

### P1 - Important (Should Have)

| Ref      | Criteria                                                                                                    | Priority |
| -------- | ----------------------------------------------------------------------------------------------------------- | -------- |
| **AC15** | Matching confidence scores are stored in database (`rekordbox_match_confidence` field) for quality tracking. | P1       |
| **AC16** | System supports filtering Amazon link search to only missing tracks (`--missing-only` flag).                 | P1       |
| **AC17** | System supports searching Amazon links for specific tracks (`--spotify-id` and `--track-id` flags).         | P1       |
| **AC18** | System supports force re-fetching of Amazon links even if already exists (`--force` flag).                  | P1       |
| **AC19** | Missing tracks report includes all relevant information: artist, title, album, Spotify URL, Amazon link.     | P1       |
| **AC20** | Database tracks can belong to multiple playlists (playlist associations preserved during deduplication).   | P1       |
| **AC21** | Normalization handles common variations: feat/ft/featuring, &/and/,, removes "original mix", "extended", etc. | P1       |
| **AC22** | Matching uses duration hints (BPM differences, time differences) to improve accuracy for borderline cases.  | P1       |

### P2 - Nice to Have (Future)

| Ref      | Criteria                                                                              | Priority |
| -------- | ------------------------------------------------------------------------------------- | -------- |
| **AC23** | Duplicate detection identifies duplicate tracks across playlists and suggests merges. | P2       |
| **AC24** | Auto-tagging suggests tags based on BPM, key, genre, energy levels.                   | P2       |
| **AC25** | Rekordbox write-back updates Rekordbox collection with database changes.               | P2       |
| **AC26** | Web UI for browsing tracks, playlists, and generating reports.                        | P2       |
| **AC27** | Export reports to various formats (CSV, JSON, HTML).                                  | P2       |
| **AC28** | Direct Spotify API integration (eliminates need for CSV exports).                    | P2       |

## Success Criteria

### Quality of Output

- **Matching Accuracy**: High-confidence matches (>= 0.7) achieve >90% accuracy (manually verified)
- **Amazon Link Success**: >70% of tracks get direct Amazon product URLs (not just search URLs)
- **Deduplication**: No duplicate tracks in database from multiple playlist imports
- **Data Integrity**: All source references (Spotify IDs, file paths) are accurate and traceable

### Performance

- **Playlist Import**: Processes 200-track playlist in < 30 seconds
- **Rekordbox Matching**: Matches 200 Spotify tracks against 22k Rekordbox tracks in < 20 minutes
- **Amazon Link Finding**: Processes 200 tracks in < 10 minutes (with rate limiting)
- **Download Scanning**: Scans 1000 files in < 2 minutes

### Cost Efficiency

- **LLM Usage**: LLM assistance only used for borderline/unmatched cases (< 30% of tracks)
- **API Calls**: Rate limiting minimizes API calls while maintaining functionality
- **Storage**: SQLite database remains manageable (< 2MB for typical collection)

### User Experience

- **CLI Usability**: Commands are intuitive and provide clear feedback
- **Error Messages**: Errors are descriptive and actionable
- **Progress Visibility**: Long operations show progress indicators
- **Manual Review**: System provides all information needed for manual verification before purchase

## Assumptions

### Product Assumptions

- **A1**: CSV export from chosic.com is reliable and available for Spotify playlists
- **A2**: Rekordbox TSV export is available and contains all necessary metadata
- **A3**: Amazon Music is the primary purchase source (other sources can be added later)
- **A4**: Manual review before purchase is acceptable (system provides links, user verifies)
- **A5**: CLI interface is sufficient for MVP (web UI is future enhancement)
- **A6**: SQLite database is manageable for typical collection sizes (< 10k tracks)

### Technical Assumptions

- **A7**: DuckDuckGo search remains reliable for finding Amazon links (bypasses bot detection)
- **A8**: Rekordbox TSV format is stable (column positions don't change)
- **A9**: Music file metadata tags are generally accurate (ID3 tags, etc.)
- **A10**: Fuzzy matching (85% threshold) balances accuracy and false positives
- **A11**: Cursor AI capabilities are available for LLM-assisted matching
- **A12**: Python 3.11+ and modern tooling (uv, pyproject.toml) are available

### Business Assumptions

- **A13**: Users will verify matches before updating Rekordbox collection
- **A14**: Missing information (no Amazon link, no match) is acceptable if clearly indicated
- **A15**: Processing time (< 20 minutes for full matching) is acceptable for one-time operations
- **A16**: Rate limiting delays are acceptable to avoid service blocking

## Questions Answered in Discussion

- [x] **Playlist Import**: CSV export from chosic.com (no direct Spotify API needed)
- [x] **Rekordbox Format**: TSV export file (not XML or database direct access)
- [x] **Matching Strategy**: Hybrid approach (deterministic + LLM for borderline cases)
- [x] **Amazon Search**: DuckDuckGo search to bypass bot detection
- [x] **Link Priority**: Track/album URLs preferred over artist pages
- [x] **Update Strategy**: Only update database when actual links found (not on failures)
- [x] **Confidence Scoring**: 0.0-1.0 scale, stored in database for tracking
- [x] **LLM Usage**: Only for borderline/unmatched cases, not all tracks
- [x] **Database Format**: SQLite database (indexed queries, atomic transactions, easy backup)
- [x] **Deduplication**: During import, not separate duplicate detection (MVP)

## Critical Open Questions

### High Priority (Block MVP Implementation)

1. **LLM Integration Method**
   - How exactly will Cursor AI be integrated for LLM-assisted matching?
   - What is the API/interface for calling Cursor AI capabilities?
   - What are the rate limits and costs?
   - **Status**: Needs technical investigation

2. **Matching Confidence Thresholds**
   - What confidence threshold should trigger LLM assistance? (suggested: < 0.7)
   - What minimum confidence is acceptable for database updates? (current: 0.6)
   - How should confidence delta work for updating existing matches? (current: 0.1)
   - **Status**: Can be tuned during testing, but needs initial values

3. **Rekordbox TSV Format Stability**
   - Are column positions guaranteed to be stable?
   - What happens if Rekordbox export format changes?
   - Should we support multiple Rekordbox export formats?
   - **Status**: Assumed stable, but needs validation

### Medium Priority (Post-MVP but Important)

4. **Duplicate Detection Strategy** (Post-MVP)
   - How should duplicates be identified? (exact match, fuzzy match, file path match)
   - Should duplicates be auto-merged or require user approval?
   - How to handle playlist associations when merging duplicates?
   - **Status**: Deferred to post-MVP

5. **Auto-tagging Rules** (Post-MVP)
   - What tags should be automatically generated?
   - How to handle conflicting tags from different sources?
   - Should tags be editable by user?
   - **Status**: Deferred to post-MVP

6. **Rekordbox Write-back Format** (Post-MVP)
   - What format should updates be exported in?
   - How to handle Rekordbox-specific fields?
   - Should updates be incremental or full sync?
   - **Status**: Deferred to post-MVP

### Low Priority (Nice to Have)

7. **Multiple Purchase Sources** (Future)
   - Should system support other purchase sources (Beatport, Bandcamp, etc.)?
   - How to prioritize sources when multiple links available?
   - **Status**: Future expansion

8. **Web UI Requirements** (Future)
   - What features should web UI provide?
   - Should it replace CLI or complement it?
   - **Status**: Future expansion

## Non-Functional Requirements

- **Type Safety**: Strong Python type hints throughout (Python 3.11+ type system)
- **Error Handling**: Failures in one track don't block others; errors are logged clearly
- **Logging**: All operations logged with timestamps for debugging and audit trails
- **Performance**: Processing completes within acceptable timeframes (< 20 min for full matching)
- **Scalability**: System handles collections up to 10k tracks in database, 22k+ Rekordbox tracks
- **Data Integrity**: Source references are always accurate; backups prevent data loss
- **Maintainability**: Code follows modern Python standards (uv, pyproject.toml, ruff, mypy)
- **Documentation**: All operations documented in spec.md and README.md

## Suggested Implementation Approach

> **Note**: These are implementation suggestions, not requirements. Detailed technical approach documented in [`spec.md`](./spec.md).

### Matching Strategy

- **Suggested approach**: Hybrid matching with deterministic phase (Phases 0-4) first, then LLM assistance (Phases 5-7) for borderline cases
- **Rationale**: Deterministic matching handles majority of cases efficiently; LLM only used when needed for accuracy

### Database Storage

- **Suggested approach**: SQLite database for performance and scalability
- **Rationale**: Fast indexed queries, atomic transactions, smaller file size than JSON, sufficient for MVP scale

### Amazon Link Finding

- **Suggested approach**: DuckDuckGo search to bypass Amazon bot detection
- **Rationale**: More reliable than direct scraping; avoids 503 errors and rate limiting

### Normalization Strategy

- **Suggested approach**: Comprehensive normalization (remove junk tokens, standardize separators, handle variations)
- **Rationale**: Improves matching accuracy by handling metadata inconsistencies

---

## Out-of-Scope (Explicit)

- Direct Spotify API integration (use CSV exports)
- Duplicate detection within database (post-MVP)
- Auto-tagging based on track qualities (post-MVP)
- Rekordbox collection write-back/updates (post-MVP)
- Multiple purchase sources (Amazon Music only for MVP)
- Web UI (CLI-only for MVP)
- Real-time playlist sync from Spotify
- Multi-user collaboration features
- Playlist management within system (read-only import)
