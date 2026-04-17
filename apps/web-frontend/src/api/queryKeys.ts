/**
 * TanStack Query keys — keep stable factories for invalidation prefixes.
 */
export const queryKeys = {
  /** Base source rows only; top-match overlay loads separately. */
  sourceTracks: (_minScore?: number) => ["sourceTracks"] as const,
  playlists: ["playlists"] as const,
  libraryTracksInfinite: ["libraryTracks", "infinite"] as const,
  matchCandidates: (sourceId: string, minScore: number) =>
    ["matchCandidates", sourceId, minScore] as const,
  /** POST /source-tracks/top-matches for a sorted id list fingerprint */
  topMatchesBatch: (minScore: number, sortedIdsKey: string) =>
    ["topMatchesBatch", minScore, sortedIdsKey] as const,
  /** Prefix to drop all cached top-match batches */
  topMatchesBatchesRoot: ["topMatchesBatch"] as const,
  matchCandidatesRoot: ["matchCandidates"] as const,
  spotifyOAuthStatus: ["spotifyOAuth", "status"] as const,
} as const;
