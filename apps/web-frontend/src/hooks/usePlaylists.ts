import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";
import { fetchPlaylists } from "@/api/endpoints";

export function usePlaylists() {
  const q = useQuery({
    queryKey: queryKeys.playlists,
    queryFn: fetchPlaylists,
    staleTime: 60_000,
  });
  return {
    data: q.data ?? null,
    isLoading: q.isLoading,
    error: q.error,
    refetch: q.refetch,
  };
}
