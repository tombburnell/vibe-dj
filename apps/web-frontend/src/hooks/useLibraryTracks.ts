import { useInfiniteQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { queryKeys } from "@/api/queryKeys";
import { fetchLibraryTracksPage } from "@/api/endpoints";
import type { LibraryTrack } from "@/api/types";

const PAGE_SIZE = 150;

export type LibraryTracksState = {
  data: LibraryTrack[];
  isLoading: boolean;
  isLoadingMore: boolean;
  error: Error | null;
  refetch: () => void;
  loadMore: () => void;
  hasMore: boolean;
};

/**
 * Keyset-paginated library tracks (server-ordered by file path).
 */
export function useLibraryTracks(): LibraryTracksState {
  const q = useInfiniteQuery({
    queryKey: queryKeys.libraryTracksInfinite,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      fetchLibraryTracksPage({
        limit: PAGE_SIZE,
        cursor: pageParam ?? undefined,
      }),
    getNextPageParam: (last) => last.next_cursor,
    staleTime: 60_000,
  });

  const data = useMemo(
    () => q.data?.pages.flatMap((p) => p.items) ?? [],
    [q.data?.pages],
  );

  return {
    data,
    isLoading: q.isPending,
    isLoadingMore: q.isFetchingNextPage,
    error: q.error,
    refetch: () => {
      void q.refetch();
    },
    loadMore: () => {
      void q.fetchNextPage();
    },
    hasMore: q.hasNextPage ?? false,
  };
}
