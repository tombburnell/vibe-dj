/** Mirrors FastAPI / Pydantic responses from `apps/api`. */

export type LibraryTrack = {
  id: string;
  user_id: string;
  library_snapshot_id: string;
  title: string;
  artist: string;
  album: string | null;
  duration_ms: number | null;
  file_path: string;
  bpm: number | null;
  musical_key: string | null;
  genre: string | null;
  created_at: string;
};

export type LibraryTrackPage = {
  items: LibraryTrack[];
  next_cursor: string | null;
};

export type Playlist = {
  id: string;
  name: string;
  import_source: string | null;
  created_at: string;
};

export type MatchCandidate = LibraryTrack & { match_score: number };

export type SourceTopMatchRow = {
  source_track_id: string;
  top_match_library_track_id: string | null;
  top_match_title: string | null;
  top_match_artist: string | null;
  top_match_score: number | null;
  top_match_duration_ms: number | null;
  top_match_is_picked: boolean;
  is_rejected_no_match: boolean;
  top_match_below_minimum: boolean;
};

export type SourceTrack = {
  id: string;
  user_id: string;
  source_kind: string;
  title: string;
  artist: string;
  album: string | null;
  duration_ms: number | null;
  spotify_id: string | null;
  spotify_url: string | null;
  on_wishlist: boolean;
  playlist_names: string[];
  local_file_path: string | null;
  downloaded_at: string | null;
  amazon_url: string | null;
  amazon_search_url: string | null;
  created_at: string;
  updated_at: string;
  /** Best match vs latest library snapshot; null if no library or no candidates. */
  top_match_title: string | null;
  top_match_artist: string | null;
  top_match_score: number | null;
  top_match_duration_ms: number | null;
  /** From batch overlay only — not set on bare GET /source-tracks. */
  top_match_library_track_id?: string | null;
  top_match_is_picked?: boolean;
  is_rejected_no_match?: boolean;
  top_match_below_minimum?: boolean;
};
