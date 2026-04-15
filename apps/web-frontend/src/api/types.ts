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
  spotify_playlist_url: string | null;
  created_at: string;
};

export type PlaylistSyncResult = {
  playlist_id: string;
  playlist_name: string;
  track_count: number;
  rows_linked: number;
  new_source_tracks: number;
};

export type MatchCandidate = LibraryTrack & {
  match_score: number;
  title_match_score: number;
  artist_match_score: number;
};

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

export type AmazonLinkCandidate = {
  url: string;
  title: string | null;
  artist: string | null;
  match_score: number | null;
  price: string | null;
  /** User-marked bad link; omitted/false for legacy rows. */
  broken?: boolean;
};

export type LocalScanMatched = {
  source_track_id: string;
  path: string;
  score: number;
  title: string;
  artist: string;
};

export type LocalScanUnmatched = {
  path: string;
  parsed_artist: string | null;
  parsed_title: string | null;
  best_score: number;
  best_source_track_id: string | null;
  best_source_artist: string | null;
  best_source_title: string | null;
  below_threshold: boolean;
  source_claimed_by_other_file: boolean;
  /** True when best overall source had a local path before this scan (auto-match only considers rows without one). */
  best_source_already_has_file?: boolean;
};

export type LocalScanResult = {
  matched: LocalScanMatched[];
  unmatched_files: string[];
  unmatched_details: LocalScanUnmatched[];
  skipped_non_audio: number;
  min_score: number;
};

export type SetLocalFileResult = {
  source_track_id: string;
  path: string;
  title: string;
  artist: string;
};

export type FindAmazonLinksResult = {
  searched_count: number;
  skipped_not_need_count: number;
  skipped_cached_count: number;
  error_count: number;
};

/** Multisite web search backend for ``findAmazonLinks`` (overrides server env for that request). */
export type WebSearchProvider = "serper" | "ddg";

/** UI: which link-search action is in progress. */
export type LinkSearchSpinTarget = WebSearchProvider | null;

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
  /** Playlist row ids (aligns with playlist_names); used for filters without resolving names client-side. */
  playlist_ids: string[];
  local_file_path: string | null;
  downloaded_at: string | null;
  amazon_url: string | null;
  amazon_search_url: string | null;
  amazon_price: string | null;
  amazon_link_title: string | null;
  amazon_link_match_score: number | null;
  amazon_last_searched_at: string | null;
  amazon_candidates: AmazonLinkCandidate[];
  created_at: string;
  updated_at: string;
  /** Best match vs latest library snapshot; null if no library or no candidates. */
  top_match_title: string | null;
  top_match_artist: string | null;
  top_match_score: number | null;
  top_match_duration_ms: number | null;
  /** Set on GET /source-tracks (min_score) and on lazy top-matches overlay. */
  top_match_library_track_id?: string | null;
  top_match_is_picked?: boolean;
  is_rejected_no_match?: boolean;
  top_match_below_minimum?: boolean;
};
