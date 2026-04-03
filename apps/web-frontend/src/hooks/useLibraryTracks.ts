import { useCallback, useEffect, useRef, useState } from "react";

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
  const [data, setData] = useState<LibraryTrack[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);
  const loadMoreInFlight = useRef(false);

  const loadFirstPage = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const page = await fetchLibraryTracksPage({ limit: PAGE_SIZE });
      setData(page.items);
      setNextCursor(page.next_cursor);
    } catch (e: unknown) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setData([]);
      setNextCursor(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFirstPage();
  }, [loadFirstPage, tick]);

  const refetch = useCallback(() => {
    setNextCursor(null);
    setTick((t) => t + 1);
  }, []);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loadMoreInFlight.current) return;
    loadMoreInFlight.current = true;
    setIsLoadingMore(true);
    setError(null);
    try {
      const page = await fetchLibraryTracksPage({
        limit: PAGE_SIZE,
        cursor: nextCursor,
      });
      setData((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (e: unknown) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      loadMoreInFlight.current = false;
      setIsLoadingMore(false);
    }
  }, [nextCursor]);

  return {
    data,
    isLoading,
    isLoadingMore,
    error,
    refetch,
    loadMore,
    hasMore: nextCursor != null,
  };
}
