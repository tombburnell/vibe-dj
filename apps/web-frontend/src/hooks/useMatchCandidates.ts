import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";
import { fetchMatchCandidates } from "@/api/endpoints";
import type { MatchCandidate, SourceTrack } from "@/api/types";

export type MatchCandidatesState = {
  data: MatchCandidate[];
  isLoading: boolean;
  error: Error | null;
};

/**
 * Ranked library candidates from `GET /api/source-tracks/:id/candidates`.
 * Invalidate with `queryClient.invalidateQueries({ queryKey: queryKeys.matchCandidatesRoot })` after match actions.
 */
export function useMatchCandidates(
  selected: SourceTrack | null,
  minScore = 0.4,
): MatchCandidatesState {
  const id = selected?.id;
  const q = useQuery({
    queryKey: queryKeys.matchCandidates(id ?? "__none__", minScore),
    queryFn: () => {
      if (!id) return Promise.resolve([]);
      return fetchMatchCandidates(id, { minScore });
    },
    enabled: Boolean(id),
    staleTime: 45_000,
  });

  return {
    data: q.data ?? [],
    isLoading: Boolean(id) && q.isLoading,
    error: q.error,
  };
}
