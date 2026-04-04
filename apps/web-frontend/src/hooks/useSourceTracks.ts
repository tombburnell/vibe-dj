import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";
import { fetchSourceTracks } from "@/api/endpoints";

export function useSourceTracks(minScore: number) {
  const q = useQuery({
    queryKey: queryKeys.sourceTracks(minScore),
    queryFn: () => fetchSourceTracks(minScore),
    staleTime: 60_000,
  });
  return {
    data: q.data ?? null,
    isLoading: q.isLoading,
    error: q.error,
    refetch: q.refetch,
  };
}
