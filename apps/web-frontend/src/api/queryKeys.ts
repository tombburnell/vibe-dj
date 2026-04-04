/**
 * TanStack Query keys — keep stable factories for invalidation prefixes.
 */
export const queryKeys = {
  /** Include min_score query param (server embeds match overlay on list). */
  sourceTracks: (minScore: number) => ["sourceTracks", minScore] as const,
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
} as const;
