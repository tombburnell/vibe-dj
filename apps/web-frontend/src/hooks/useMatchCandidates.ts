import { useEffect, useState } from "react";

import { fetchMatchCandidates } from "@/api/endpoints";
import type { MatchCandidate, SourceTrack } from "@/api/types";

export type MatchCandidatesState = {
  data: MatchCandidate[];
  isLoading: boolean;
  error: Error | null;
};

/**
 * Loads ranked library candidates from `GET /api/source-tracks/:id/candidates`.
 */
export function useMatchCandidates(
  selected: SourceTrack | null,
  minScore = 0.4,
  refreshEpoch = 0,
): MatchCandidatesState {
  const [data, setData] = useState<MatchCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!selected) {
      setData([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetchMatchCandidates(selected.id, { minScore })
      .then((rows) => {
        if (!cancelled) {
          setData(rows);
          setIsLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e : new Error(String(e)));
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selected?.id, minScore, refreshEpoch]);

  return { data, isLoading, error };
}
