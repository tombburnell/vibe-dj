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

export type MatchCandidate = LibraryTrack & { match_score: number };

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
};
