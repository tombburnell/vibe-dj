import { apiDelete, apiGet, apiPostFormData, apiPostJson } from "./client";
import type {
  FindAmazonLinksResult,
  LibraryTrackPage,
  MatchCandidate,
  Playlist,
  SourceTopMatchRow,
  SourceTrack,
} from "./types";

const DEFAULT_LIBRARY_PAGE = 150;

export function fetchLibraryTracksPage(params: {
  limit?: number;
  cursor?: string | null;
  snapshotId?: string | null;
} = {}): Promise<LibraryTrackPage> {
  const sp = new URLSearchParams();
  sp.set("limit", String(params.limit ?? DEFAULT_LIBRARY_PAGE));
  if (params.cursor) sp.set("cursor", params.cursor);
  if (params.snapshotId) sp.set("snapshot_id", params.snapshotId);
  return apiGet<LibraryTrackPage>(`/api/library-tracks?${sp.toString()}`);
}

function normalizeSourceTrack(r: SourceTrack): SourceTrack {
  return {
    ...r,
    amazon_candidates: r.amazon_candidates ?? [],
    amazon_price: r.amazon_price ?? null,
    amazon_link_title: r.amazon_link_title ?? null,
    amazon_link_match_score: r.amazon_link_match_score ?? null,
    amazon_last_searched_at: r.amazon_last_searched_at ?? null,
    top_match_library_track_id: r.top_match_library_track_id ?? null,
    top_match_is_picked: r.top_match_is_picked ?? false,
    is_rejected_no_match: r.is_rejected_no_match ?? false,
    top_match_below_minimum: r.top_match_below_minimum ?? false,
  };
}

export function fetchSourceTracks(minScore = 0.4): Promise<SourceTrack[]> {
  const sp = new URLSearchParams();
  sp.set("min_score", String(minScore));
  return apiGet<SourceTrack[]>(`/api/source-tracks?${sp.toString()}`).then((rows) =>
    rows.map((row) => normalizeSourceTrack(row)),
  );
}

export function postSourceTopMatches(
  sourceTrackIds: string[],
  options: { minScore?: number } = {},
): Promise<SourceTopMatchRow[]> {
  return apiPostJson<SourceTopMatchRow[]>("/api/source-tracks/top-matches", {
    source_track_ids: sourceTrackIds.slice(0, 100),
    min_score: options.minScore ?? 0.4,
  });
}

export function findAmazonLinks(body: {
  source_track_ids?: string[];
  force?: boolean;
}): Promise<FindAmazonLinksResult> {
  return apiPostJson<FindAmazonLinksResult>("/api/source-tracks/find-amazon-links", {
    source_track_ids: body.source_track_ids ?? [],
    force: body.force ?? false,
  });
}

export function sourceWishlistBatch(
  sourceTrackIds: string[],
  onWishlist: boolean,
): Promise<{ ok: boolean; updated_count: number }> {
  return apiPostJson("/api/source-tracks/wishlist-batch", {
    source_track_ids: sourceTrackIds,
    on_wishlist: onWishlist,
  });
}

export function fetchPlaylists(): Promise<Playlist[]> {
  return apiGet<Playlist[]>("/api/playlists");
}

export function deletePlaylist(playlistId: string): Promise<void> {
  return apiDelete(`/api/playlists/${encodeURIComponent(playlistId)}`);
}

export function fetchMatchCandidates(
  sourceId: string,
  options: { minScore?: number } = {},
): Promise<MatchCandidate[]> {
  const sp = new URLSearchParams();
  sp.set("min_score", String(options.minScore ?? 0.4));
  return apiGet<MatchCandidate[]>(
    `/api/source-tracks/${encodeURIComponent(sourceId)}/candidates?${sp.toString()}`,
  );
}

export function matchPick(
  sourceTrackId: string,
  libraryTrackId: string,
  matchScore: number | null,
): Promise<{ ok: boolean }> {
  return apiPostJson("/api/match/pick", {
    source_track_id: sourceTrackId,
    library_track_id: libraryTrackId,
    match_score: matchScore,
  });
}

export function matchReject(sourceTrackId: string): Promise<{ ok: boolean }> {
  return apiPostJson("/api/match/reject", {
    source_track_id: sourceTrackId,
  });
}

export function matchRejectBatch(
  sourceTrackIds: string[],
): Promise<{ ok: boolean; rejected_count: number }> {
  return apiPostJson("/api/match/reject/batch", {
    source_track_ids: sourceTrackIds,
  });
}

export function matchUndoPick(sourceTrackId: string): Promise<void> {
  return apiDelete(`/api/match/pick/${encodeURIComponent(sourceTrackId)}`);
}

export function matchUndoReject(sourceTrackId: string): Promise<void> {
  return apiDelete(`/api/match/reject/${encodeURIComponent(sourceTrackId)}`);
}

export function matchUndoAuto(sourceTrackId: string): Promise<void> {
  return apiDelete(`/api/match/auto/${encodeURIComponent(sourceTrackId)}`);
}

export function importLibrarySnapshot(file: File, label?: string): Promise<{
  snapshot_id: string;
  track_count: number;
}> {
  const fd = new FormData();
  fd.append("file", file);
  if (label?.trim()) fd.append("label", label.trim());
  return apiPostFormData("/api/library-snapshots/import", fd);
}

export function importPlaylistCsv(
  file: File,
  importSource = "chosic_csv",
): Promise<{ playlist_id: string; rows_linked: number; new_source_tracks: number }> {
  const fd = new FormData();
  // Explicit filename helps proxies/servers that omit multipart Content-Disposition name.
  fd.append("file", file, file.name);
  if (file.name?.trim()) {
    fd.append("client_filename", file.name);
  }
  fd.append("import_source", importSource);
  return apiPostFormData("/api/playlists/import", fd);
}

export function runMatchJob(body: {
  library_snapshot_id?: string | null;
  min_confidence?: number;
} = {}): Promise<{ library_snapshot_id: string | null; matched_count: number; skipped_count: number }> {
  return apiPostJson("/api/match/run", body);
}
