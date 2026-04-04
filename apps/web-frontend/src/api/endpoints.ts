import { apiDelete, apiGet, apiPostFormData, apiPostJson } from "./client";
import type {
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

export function fetchSourceTracks(): Promise<SourceTrack[]> {
  return apiGet<SourceTrack[]>("/api/source-tracks");
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
