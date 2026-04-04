import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";

import { postSourceTopMatches } from "@/api/endpoints";
import type { SourceTopMatchRow } from "@/api/types";

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
 */
export function useVisibleSourceTopMatches(
  scrollRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
  listFingerprint: string,
  /** Bumps scroll/attach effects when rows appear (e.g. 0 → N). */
  rowCount: number,
  options: Options = {},
) {
  const { onFetchError, minScore = 0.4, suspendAutoFetch = false } = options;
  const onFetchErrorRef = useRef(onFetchError);
  onFetchErrorRef.current = onFetchError;

  const [overlay, setOverlay] = useState<TopMatchOverlay>({});
  const [loadingIds, setLoadingIds] = useState(() => new Set<string>());
  const fetchedRef = useRef(new Set<string>());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef(false);

  useEffect(() => {
    setOverlay({});
    fetchedRef.current = new Set();
    setLoadingIds(new Set());
  }, [listFingerprint]);

  const runBatch = useCallback(async () => {
    const el = scrollRef.current;
    if (!el || !enabled || suspendAutoFetch || inFlightRef.current) return;

    inFlightRef.current = true;
    try {
      for (let round = 0; round < MAX_ROUNDS_PER_SCHEDULE; round++) {
        const visible = visibleDataRowIds(el);
        const need = visible.filter((id) => !fetchedRef.current.has(id));
        const toFetch = need.slice(0, MAX_BATCH);
        if (toFetch.length === 0) break;

        toFetch.forEach((id) => fetchedRef.current.add(id));
        setLoadingIds((prev) => new Set([...prev, ...toFetch]));

        try {
          const rows = await postSourceTopMatches(toFetch, { minScore });
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
  }, [enabled, scrollRef, minScore, suspendAutoFetch]);

  /** Merge API top-match rows without clearing the rest of the overlay (e.g. after pick). */
  const applyTopMatchRows = useCallback((rows: SourceTopMatchRow[]) => {
    if (rows.length === 0) return;
    const patch: TopMatchOverlay = {};
    for (const r of rows) {
      patch[r.source_track_id] = overlayFromRow(r);
    }
    setOverlay((o) => ({ ...o, ...patch }));
    for (const r of rows) {
      fetchedRef.current.add(r.source_track_id);
    }
  }, []);

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
