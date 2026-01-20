# ChatGPT Prompt for Track Matching

Copy and paste this prompt into ChatGPT along with your `music_db.json` and `all-tracks.txt` files:

---

## Task: Match Spotify Tracks with Rekordbox Collection

I have two datasets:
1. **Spotify tracks** (from `music_db.json`) - tracks from playlists I want to match
2. **Rekordbox collection** (from `all-tracks.txt`) - my existing music library (22k+ tracks)

I need you to match each Spotify track with the best corresponding track in my Rekordbox collection.

### Important Context:

**Metadata Quality Issues:**
- Rekordbox metadata is often messy - artist names and track titles may be swapped
- Track titles in Rekordbox may include remix info, extra text, or be incomplete
- Artist names may be formatted differently (e.g., "Artist, Feat. Other" vs "Artist Feat. Other")
- Some tracks may have artist names in the title field and vice versa

**Matching Strategy:**
- **Primary signals**: Track title and artist name (but be flexible with formatting)
- **Supporting hints**: 
  - **Duration** (`duration_ms` in Spotify vs `Time` MM:SS in Rekordbox) - use as a hint, but note that different edits (radio vs extended mix) will have different durations
  - **BPM** (only in Rekordbox) - use as a hint if available
  - **Genre** (only in Rekordbox) - use as a hint if available
  - **Album** - use as a hint if both have album info

**Confidence Scoring:**
- **0.9-1.0**: Excellent match - title and artist clearly match, duration/BPM/genre align
- **0.7-0.89**: Good match - title and artist match with minor variations, supporting hints align
- **0.6-0.69**: Fair match - title or artist has some differences but likely the same track
- **0.5-0.59**: Weak match - some similarity but uncertain
- **<0.5**: No match found or too uncertain

### Data Format:

**Spotify tracks** (from music_db.json):
- `id`: Database track ID (use this in output)
- `title`: Track title
- `artist`: Artist name
- `album`: Album name (may be null)
- `duration_ms`: Duration in milliseconds (may be null)

**Rekordbox tracks** (from all-tracks.txt, tab-separated):
- Column 7: Track Title
- Column 8: Artist
- Column 12: Genre
- Column 13: Album
- Column 3: BPM (may be empty)
- Column 5: Key (may be empty)
- Column 6: Time (MM:SS format)
- Column 15: Location (file path - this is what you need to return)

### Output Format:

Return a JSON array with matches. For each Spotify track that has a match:

```json
[
  {
    "id": "spotify_0sQDaCCZDNsdSBnP66Z8BN",
    "rekordbox_file_path": "/Users/tomburnell/Dropbox/Music/Tracks/techno/.../track.mp3",
    "confidence": 0.85
  },
  ...
]
```

**Rules:**
- Only include matches with confidence >= 0.6
- If no good match found for a track, omit it from the results
- If multiple potential matches exist, choose the best one (highest confidence)
- Convert Rekordbox `Time` (MM:SS) to milliseconds for comparison: `(minutes * 60 + seconds) * 1000`
- The `rekordbox_file_path` should be the exact `Location` value from the TSV file

### Example Matching Scenarios:

1. **Good match**: Spotify "Untold" by "Octave One" matches Rekordbox "Untold" by "Octave One" with similar duration → confidence 0.9

2. **Formatting differences**: Spotify "Showbiz Feat. Villa" by "Yuksek" matches Rekordbox "Showbiz Feat. Villa (Purple Disco Machine Edit)" by "Yuksek" → confidence 0.85 (remix info in title is fine)

3. **Metadata swap**: Spotify track where artist/title might be swapped - use BPM, genre, duration to help disambiguate

4. **Different edits**: Same track but different durations (e.g., radio edit vs extended mix) - still match if title/artist match → confidence 0.8-0.9

5. **No match**: Track doesn't exist in Rekordbox → omit from results

### Instructions:

1. Parse both datasets
2. For each Spotify track, find the best matching Rekordbox track
3. Calculate confidence score based on title/artist similarity and supporting hints
4. Return JSON array with matches (confidence >= 0.6 only)

Please process all tracks and return the complete JSON array of matches.
