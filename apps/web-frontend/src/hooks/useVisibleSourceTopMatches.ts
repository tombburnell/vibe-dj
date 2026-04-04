import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";

import { queryKeys } from "@/api/queryKeys";
import { postSourceTopMatches } from "@/api/endpoints";
import type { SourceTopMatchRow, SourceTrack } from "@/api/types";

export type TopMatchOverlay = Record<
  string,
  {
    top_match_library_track_id: string | null;
    top_match_title: string | null;
    top_match_artist: string | null;
    top_match_score: number | null;
    top_match_duration_ms: number | null;
    top_match_is_picked: boolean;
    is_rejected_no_match: boolean;
    top_match_below_minimum: boolean;
  }
>;

const DEBOUNCE_MS = 120;
const MAX_BATCH = 80;
const MAX_ROUNDS_PER_SCHEDULE = 12;
const OVERSCAN_PX = 72;
const TOP_MATCH_BATCH_STALE_MS = 5 * 60 * 1000;

function overlayFromRow(r: SourceTopMatchRow): TopMatchOverlay[string] {
  return {
    top_match_library_track_id: r.top_match_library_track_id,
    top_match_title: r.top_match_title,
    top_match_artist: r.top_match_artist,
    top_match_score: r.top_match_score,
    top_match_duration_ms: r.top_match_duration_ms,
    top_match_is_picked: r.top_match_is_picked,
    is_rejected_no_match: r.is_rejected_no_match,
    top_match_below_minimum: r.top_match_below_minimum ?? false,
  };
}

/** Rebuild overlay + fetched set from TanStack cache (survives Workspace unmount). */
function hydrateTopMatchOverlayFromCache(
  queryClient: QueryClient,
  minScore: number,
): { overlay: TopMatchOverlay; fetchedIds: Set<string> } {
  const entries = queryClient.getQueriesData<SourceTopMatchRow[]>({
    queryKey: queryKeys.topMatchesBatchesRoot,
  });
  const overlay: TopMatchOverlay = {};
  const fetchedIds = new Set<string>();
  for (const [key, data] of entries) {
    if (!Array.isArray(key) || key.length < 3) continue;
    if (key[0] !== "topMatchesBatch" || key[1] !== minScore) continue;
    if (!data?.length) continue;
    for (const r of data) {
      overlay[r.source_track_id] = overlayFromRow(r);
      fetchedIds.add(r.source_track_id);
    }
  }
  return { overlay, fetchedIds };
}

function visibleDataRowIds(container: HTMLElement): string[] {
  const cr = container.getBoundingClientRect();
  const rows = container.querySelectorAll<HTMLElement>("tbody tr[data-row-id]");
  const ids: string[] = [];
  rows.forEach((tr) => {
    const r = tr.getBoundingClientRect();
    if (
      r.bottom >= cr.top - OVERSCAN_PX &&
      r.top <= cr.bottom + OVERSCAN_PX
    ) {
      const id = tr.getAttribute("data-row-id");
      if (id) ids.push(id);
    }
  });
  return ids;
}

type Options = {
  onFetchError?: (err: Error) => void;
  /** API fuzzy floor 0–1 (default 0.4). */
  minScore?: number;
  /** When true, skip scroll/resize-driven batch fetches (e.g. while Run matching + bulk refresh runs). */
  suspendAutoFetch?: boolean;
};

/**
 * Fetches best-match overlays for table rows intersecting the scroll container
 * (debounced). Resets when `listFingerprint` changes (e.g. filter / refetch).
 * Batches are cached via TanStack Query (`topMatchesBatch` keys).
 *
 * Rows already **Missing** or **picked** (merged state) skip network fetch — list GET embeds that state.
 */
export function useVisibleSourceTopMatches(
  scrollRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
  listFingerprint: string,
  /** Bumps scroll/attach effects when rows appear (e.g. 0 → N). */
  rowCount: number,
  mergedSourcesRef: RefObject<SourceTrack[]>,
  options: Options = {},
) {
  const queryClient = useQueryClient();
  const { onFetchError, minScore = 0.4, suspendAutoFetch = false } = options;
  const onFetchErrorRef = useRef(onFetchError);
  onFetchErrorRef.current = onFetchError;

  const [overlay, setOverlay] = useState<TopMatchOverlay>({});
  const [loadingIds, setLoadingIds] = useState(() => new Set<string>());
  const fetchedRef = useRef(new Set<string>());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef(false);
  const prevFingerprintRef = useRef<string | null>(null);

  /**
   * - First mount (e.g. return from Settings): hydrate overlay from cached top-match batches;
   *   do not removeQueries or we wipe the cache and refetch everything.
   * - Fingerprint change (filters, min score, source list): clear local state + drop batch cache.
   */
  useLayoutEffect(() => {
    const prev = prevFingerprintRef.current;
    if (prev === null) {
      const { overlay: cached, fetchedIds } = hydrateTopMatchOverlayFromCache(
        queryClient,
        minScore,
      );
      if (Object.keys(cached).length > 0) {
        setOverlay(cached);
        fetchedRef.current = fetchedIds;
      }
      prevFingerprintRef.current = listFingerprint;
      return;
    }
    if (prev !== listFingerprint) {
      setOverlay({});
      fetchedRef.current = new Set();
      setLoadingIds(new Set());
      queryClient.removeQueries({ queryKey: queryKeys.topMatchesBatchesRoot });
      prevFingerprintRef.current = listFingerprint;
    }
  }, [listFingerprint, queryClient, minScore]);

  const runBatch = useCallback(async () => {
    const el = scrollRef.current;
    if (!el || !enabled || suspendAutoFetch || inFlightRef.current) return;

    inFlightRef.current = true;
    try {
      for (let round = 0; round < MAX_ROUNDS_PER_SCHEDULE; round++) {
        const visible = visibleDataRowIds(el);
        const merged = mergedSourcesRef.current;
        for (const id of visible) {
          if (fetchedRef.current.has(id)) continue;
          const m = merged.find((r) => r.id === id);
          if (
            m?.is_rejected_no_match === true ||
            m?.top_match_is_picked === true
          ) {
            fetchedRef.current.add(id);
          }
        }
        const need = visible.filter((id) => !fetchedRef.current.has(id));
        const toFetch = need.slice(0, MAX_BATCH);
        if (toFetch.length === 0) break;

        toFetch.forEach((id) => fetchedRef.current.add(id));
        setLoadingIds((prev) => new Set([...prev, ...toFetch]));

        const sortedIds = [...toFetch].sort();
        const sortedKey = sortedIds.join(",");

        try {
          const rows = await queryClient.fetchQuery({
            queryKey: queryKeys.topMatchesBatch(minScore, sortedKey),
            queryFn: () => postSourceTopMatches(sortedIds, { minScore }),
            staleTime: TOP_MATCH_BATCH_STALE_MS,
          });
          const patch: TopMatchOverlay = {};
          for (const r of rows) {
            patch[r.source_track_id] = overlayFromRow(r);
          }
          setOverlay((o) => ({ ...o, ...patch }));
        } catch (e) {
          toFetch.forEach((id) => fetchedRef.current.delete(id));
          const err = e instanceof Error ? e : new Error(String(e));
          onFetchErrorRef.current?.(err);
          break;
        } finally {
          setLoadingIds((prev) => {
            const n = new Set(prev);
            toFetch.forEach((id) => n.delete(id));
            return n;
          });
        }
      }
    } finally {
      inFlightRef.current = false;
    }
  }, [enabled, scrollRef, minScore, suspendAutoFetch, queryClient, mergedSourcesRef]);

  /** Merge API top-match rows without clearing the rest of the overlay (e.g. after pick). */
  const applyTopMatchRows = useCallback(
    (rows: SourceTopMatchRow[]) => {
      if (rows.length === 0) return;
      const patch: TopMatchOverlay = {};
      for (const r of rows) {
        patch[r.source_track_id] = overlayFromRow(r);
      }
      setOverlay((o) => ({ ...o, ...patch }));
      for (const r of rows) {
        fetchedRef.current.add(r.source_track_id);
      }
    },
    [],
  );

  const schedule = useCallback(() => {
    if (suspendAutoFetch) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      void runBatch();
    }, DEBOUNCE_MS);
  }, [runBatch, suspendAutoFetch]);

  useEffect(() => {
    if (suspendAutoFetch && timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, [suspendAutoFetch]);

  useEffect(() => {
    if (!enabled || suspendAutoFetch) return;
    schedule();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [enabled, listFingerprint, schedule, suspendAutoFetch]);

  useEffect(() => {
    if (!enabled || suspendAutoFetch) return;
    const id = requestAnimationFrame(() => schedule());
    return () => cancelAnimationFrame(id);
  }, [enabled, listFingerprint, schedule, suspendAutoFetch]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !enabled || suspendAutoFetch) return;
    el.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    return () => {
      el.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [enabled, suspendAutoFetch, scrollRef, schedule, listFingerprint, rowCount]);

  return { overlay, loadingIds, applyTopMatchRows };
}
