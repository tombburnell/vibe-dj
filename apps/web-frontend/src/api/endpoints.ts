import { apiGet, apiPostFormData, apiPostJson } from "./client";
import type { LibraryTrackPage, MatchCandidate, SourceTrack } from "./types";

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

export function fetchMatchCandidates(sourceId: string): Promise<MatchCandidate[]> {
  return apiGet<MatchCandidate[]>(
    `/api/source-tracks/${encodeURIComponent(sourceId)}/candidates`,
  );
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
  playlistName: string,
  importSource = "chosic_csv",
): Promise<{ playlist_id: string; rows_linked: number; new_source_tracks: number }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("playlist_name", playlistName);
  fd.append("import_source", importSource);
  return apiPostFormData("/api/playlists/import", fd);
}

export function runMatchJob(body: {
  library_snapshot_id?: string | null;
  min_confidence?: number;
} = {}): Promise<{ library_snapshot_id: string | null; matched_count: number; skipped_count: number }> {
  return apiPostJson("/api/match/run", body);
}
