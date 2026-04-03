import { apiGet } from "./client";
import type { LibraryTrack, SourceTrack } from "./types";

export function fetchLibraryTracks(): Promise<LibraryTrack[]> {
  return apiGet<LibraryTrack[]>("/api/library-tracks");
}

export function fetchSourceTracks(): Promise<SourceTrack[]> {
  return apiGet<SourceTrack[]>("/api/source-tracks");
}
