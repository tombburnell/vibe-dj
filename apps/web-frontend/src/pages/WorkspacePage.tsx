import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";

import type { MatchCandidate } from "@/api/types";
import {
  importLibrarySnapshot,
  importPlaylistCsv,
  matchPick,
  matchReject,
  matchUndoPick,
  matchUndoReject,
  postSourceTopMatches,
  runMatchJob,
} from "@/api/endpoints";
import type { LibraryTrack } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import { AppShell } from "@/components/layout/AppShell";
import { WorkspaceLayout } from "@/components/layout/WorkspaceLayout";
import { DataTable } from "@/components/tables/DataTable";
import { buildLibraryTrackColumns } from "@/components/tables/columns/libraryTrackColumns";
import { buildSourceTrackColumns } from "@/components/tables/columns/sourceTrackColumns";
import { TableSkeleton } from "@/components/ui/TableSkeleton";
import { DlFilterSelect, type DlFilter } from "@/components/workspace/DlFilterSelect";
import { MainViewTabs, type MainView } from "@/components/workspace/MainViewTabs";
import { SourceMatchCategoryFilter } from "@/components/workspace/SourceMatchCategoryFilter";
import { SecondaryPanel } from "@/components/workspace/SecondaryPanel";
import { SourceTopMatchContext } from "@/contexts/SourceTopMatchContext";
import { useLibraryTracks } from "@/hooks/useLibraryTracks";
import { useMatchCandidates } from "@/hooks/useMatchCandidates";
import { useSourceTracks } from "@/hooks/useSourceTracks";
import { useVisibleSourceTopMatches } from "@/hooks/useVisibleSourceTopMatches";
import { useToast } from "@/providers/ToastProvider";
import {
  defaultSourceMatchCategoryFilter,
  sourcePassesCategoryFilter,
  type SourceMatchCategoryFilterState,
} from "@/lib/sourceMatchCategory";

function filterSourcesByDl(rows: SourceTrack[], dl: DlFilter): SourceTrack[] {
  if (dl === "downloaded") return rows.filter((s) => Boolean(s.local_file_path));
  if (dl === "not_downloaded") return rows.filter((s) => !s.local_file_path);
  return rows;
}

export function WorkspacePage() {
  const { showToast } = useToast();
  const sourceQuery = useSourceTracks();
  const libraryQuery = useLibraryTracks();
  const [mainView, setMainView] = useState<MainView>("sources");
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedLibraryId, setSelectedLibraryId] = useState<string | null>(null);
  const [dlFilter, setDlFilter] = useState<DlFilter>("all");
  const [matchCategoryFilter, setMatchCategoryFilter] =
    useState<SourceMatchCategoryFilterState>(defaultSourceMatchCategoryFilter);
  const [topMatchEpoch, setTopMatchEpoch] = useState(0);
  const [minMatchScore, setMinMatchScore] = useState(0.4);
  const [matchRefreshEpoch, setMatchRefreshEpoch] = useState(0);
  const [matchActionBusy, setMatchActionBusy] = useState(false);
  const [runMatchingBusy, setRunMatchingBusy] = useState(false);
  const libraryFileRef = useRef<HTMLInputElement>(null);
  const playlistFileRef = useRef<HTMLInputElement>(null);
  const sourceScrollRef = useRef<HTMLDivElement>(null);
  const sourceDisplayOrderRef = useRef<string[]>([]);
  const sourceShiftAnchorRef = useRef<string | null>(null);

  const onSourceDisplayRowOrder = useCallback((ids: string[]) => {
    sourceDisplayOrderRef.current = ids;
  }, []);

  const sourceColumns = useMemo(() => buildSourceTrackColumns(), []);
  const libraryColumns = useMemo(() => buildLibraryTrackColumns(), []);

  const filteredSources = useMemo(() => {
    const rows = sourceQuery.data ?? [];
    if (dlFilter === "downloaded") return rows.filter((s) => Boolean(s.local_file_path));
    if (dlFilter === "not_downloaded") return rows.filter((s) => !s.local_file_path);
    return rows;
  }, [sourceQuery.data, dlFilter]);

  const listFingerprint = useMemo(
    () =>
      `${topMatchEpoch}:${minMatchScore}:${filteredSources.map((s) => s.id).sort().join(",")}`,
    [filteredSources, topMatchEpoch, minMatchScore],
  );

  const { overlay, loadingIds, applyTopMatchRows } = useVisibleSourceTopMatches(
    sourceScrollRef,
    mainView === "sources" &&
      !sourceQuery.isLoading &&
      filteredSources.length > 0,
    listFingerprint,
    filteredSources.length,
    {
      onFetchError: (e) => showToast(e.message, "error"),
      minScore: minMatchScore,
      suspendAutoFetch: runMatchingBusy,
    },
  );

  const mergedSources = useMemo(
    () =>
      filteredSources.map((s) => ({
        ...s,
        ...(overlay[s.id] ?? {}),
      })),
    [filteredSources, overlay],
  );

  const displaySources = useMemo(
    () => mergedSources.filter((s) => sourcePassesCategoryFilter(s, matchCategoryFilter)),
    [mergedSources, matchCategoryFilter],
  );

  const topMatchCtx = useMemo(
    () => ({
      isTopMatchLoading: (id: string) => loadingIds.has(id),
    }),
    [loadingIds],
  );

  const sourceSelectionCount = selectedSourceIds.length;

  const selectedSource = useMemo(() => {
    if (selectedSourceIds.length !== 1) return null;
    return mergedSources.find((s) => s.id === selectedSourceIds[0]) ?? null;
  }, [mergedSources, selectedSourceIds]);

  const selectedSourcesBulk = useMemo((): SourceTrack[] => {
    if (selectedSourceIds.length <= 1) return [];
    const out: SourceTrack[] = [];
    for (const id of selectedSourceIds) {
      const s = mergedSources.find((x) => x.id === id);
      if (s) out.push(s);
    }
    return out;
  }, [mergedSources, selectedSourceIds]);

  const libraryRows = libraryQuery.data ?? [];
  const selectedLibrary = useMemo(
    () => libraryRows.find((l) => l.id === selectedLibraryId) ?? null,
    [libraryRows, selectedLibraryId],
  );

  const matchCandidates = useMatchCandidates(
    mainView === "sources" ? selectedSource : null,
    minMatchScore,
    matchRefreshEpoch,
  );

  const bumpMatchData = () => {
    setTopMatchEpoch((e) => e + 1);
    setMatchRefreshEpoch((e) => e + 1);
  };

  /** Match mutations: refresh only this source’s overlay + candidates panel (no full table refetch). */
  const withMatchActionForSource = async (
    sourceTrackId: string,
    fn: () => Promise<unknown>,
  ) => {
    await withMatchActionForSources([sourceTrackId], fn);
  };

  const withMatchActionForSources = async (
    sourceTrackIds: string[],
    fn: () => Promise<unknown>,
  ) => {
    const uniq = [...new Set(sourceTrackIds)].filter(Boolean).slice(0, 100);
    setMatchActionBusy(true);
    try {
      await fn();
      if (uniq.length === 0) return;
      const rows = await postSourceTopMatches(uniq, {
        minScore: minMatchScore,
      });
      applyTopMatchRows(rows);
      setMatchRefreshEpoch((e) => e + 1);
    } catch (err) {
      showToast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setMatchActionBusy(false);
    }
  };

  const handleSourceRowClick = (row: SourceTrack, e?: MouseEvent<HTMLTableRowElement>) => {
    const id = row.id;
    const order = sourceDisplayOrderRef.current;

    if (e?.shiftKey && sourceShiftAnchorRef.current && order.length > 0) {
      const a = order.indexOf(sourceShiftAnchorRef.current);
      const b = order.indexOf(id);
      if (a >= 0 && b >= 0) {
        const lo = Math.min(a, b);
        const hi = Math.max(a, b);
        setSelectedSourceIds(order.slice(lo, hi + 1));
        return;
      }
    }

    if (e?.metaKey || e?.ctrlKey) {
      setSelectedSourceIds((prev) =>
        prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
      );
      sourceShiftAnchorRef.current = id;
      return;
    }

    setSelectedSourceIds([id]);
    sourceShiftAnchorRef.current = id;
  };

  const runPickSelectedMatches = () => {
    const targets: SourceTrack[] = [];
    for (const sid of selectedSourceIds) {
      const s = mergedSources.find((x) => x.id === sid);
      if (!s) continue;
      if (
        s.top_match_library_track_id != null &&
        s.top_match_score != null &&
        !s.is_rejected_no_match &&
        !s.top_match_is_picked &&
        !s.top_match_below_minimum
      ) {
        targets.push(s);
      }
    }
    if (targets.length === 0) {
      showToast(
        "No eligible rows (need a best match; not rejected or already picked).",
        "info",
      );
      return;
    }
    void withMatchActionForSources(selectedSourceIds, async () => {
      for (const s of targets) {
        await matchPick(s.id, s.top_match_library_track_id!, s.top_match_score);
      }
      showToast(`Picked ${targets.length} match(es).`, "info");
    });
  };

  const runRejectSelectedMatches = () => {
    if (selectedSourceIds.length === 0) return;
    const n = selectedSourceIds.length;
    void withMatchActionForSources(selectedSourceIds, async () => {
      for (const sid of selectedSourceIds) {
        await matchReject(sid);
      }
      showToast(`Rejected ${n} track(s).`, "info");
    });
  };

  useEffect(() => {
    if (sourceQuery.error) showToast(sourceQuery.error.message, "error");
  }, [sourceQuery.error, showToast]);

  useEffect(() => {
    if (libraryQuery.error) showToast(libraryQuery.error.message, "error");
  }, [libraryQuery.error, showToast]);

  useEffect(() => {
    const visible = new Set(displaySources.map((s) => s.id));
    setSelectedSourceIds((prev) => prev.filter((id) => visible.has(id)));
  }, [displaySources]);

  const primaryLoading =
    mainView === "sources"
      ? sourceQuery.isLoading
      : libraryQuery.isLoading && libraryQuery.data.length === 0;

  return (
    <AppShell>
      <WorkspaceLayout
        toolbar={
          <div className="flex flex-wrap items-center gap-3">
            <MainViewTabs value={mainView} onChange={setMainView} />
            {mainView === "sources" ? (
              <>
                <DlFilterSelect value={dlFilter} onChange={setDlFilter} />
                <SourceMatchCategoryFilter
                  value={matchCategoryFilter}
                  onChange={setMatchCategoryFilter}
                />
              </>
            ) : null}
            <input
              ref={libraryFileRef}
              type="file"
              accept=".tsv,text/tab-separated-values"
              className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (!f) return;
                try {
                  const r = await importLibrarySnapshot(f);
                  showToast(`Library import: ${r.track_count} tracks`, "info");
                  libraryQuery.refetch();
                  bumpMatchData();
                } catch (err) {
                  showToast(err instanceof Error ? err.message : String(err), "error");
                }
              }}
            />
            <button
              type="button"
              className="rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-1"
              onClick={() => libraryFileRef.current?.click()}
            >
              Import Rekordbox TSV
            </button>
            <input
              ref={playlistFileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (!f) return;
                try {
                  const r = await importPlaylistCsv(f);
                  showToast(
                    `Playlist: linked ${r.rows_linked}, new sources ${r.new_source_tracks}`,
                    "info",
                  );
                  sourceQuery.refetch();
                } catch (err) {
                  showToast(err instanceof Error ? err.message : String(err), "error");
                }
              }}
            />
            <button
              type="button"
              className="rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-1"
              onClick={() => playlistFileRef.current?.click()}
            >
              Import playlist CSV
            </button>
            <label className="flex items-center gap-1.5 text-[0.75rem] text-secondary">
              <span className="whitespace-nowrap">Min match</span>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={Math.round(minMatchScore * 100)}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (!Number.isFinite(n)) return;
                  setMinMatchScore(Math.min(100, Math.max(0, n)) / 100);
                }}
                className="w-14 rounded border border-border/80 bg-surface-1 px-1 py-0.5 tabular-nums text-primary"
              />
              <span>%</span>
            </label>
            <button
              type="button"
              disabled={runMatchingBusy}
              aria-busy={runMatchingBusy}
              className="inline-flex items-center gap-1.5 rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={async () => {
                setRunMatchingBusy(true);
                try {
                  const r = await runMatchJob({});
                  showToast(
                    `Match: ${r.matched_count} auto-linked, ${r.skipped_count} skipped`,
                    "info",
                  );
                  const rows = sourceQuery.data ?? [];
                  const ids = filterSourcesByDl(rows, dlFilter).map((s) => s.id);
                  for (let i = 0; i < ids.length; i += 100) {
                    const chunk = ids.slice(i, i + 100);
                    const batch = await postSourceTopMatches(chunk, {
                      minScore: minMatchScore,
                    });
                    applyTopMatchRows(batch);
                  }
                  setMatchRefreshEpoch((e) => e + 1);
                } catch (err) {
                  showToast(err instanceof Error ? err.message : String(err), "error");
                } finally {
                  setRunMatchingBusy(false);
                }
              }}
            >
              {runMatchingBusy ? (
                <>
                  <span
                    className="inline-block size-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent opacity-80"
                    aria-hidden
                  />
                  <span>Matching…</span>
                </>
              ) : (
                "Run matching"
              )}
            </button>
          </div>
        }
        primary={
          <div className="flex min-h-0 flex-1 flex-col gap-1">
            <h2 className="shrink-0 text-[0.7rem] font-semibold uppercase tracking-wide text-muted">
              {mainView === "sources" ? "Source tracks" : "Library tracks"}
            </h2>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {primaryLoading ? (
                <TableSkeleton rows={10} cols={6} />
              ) : mainView === "sources" ? (
                <SourceTopMatchContext.Provider value={topMatchCtx}>
                  <DataTable<SourceTrack>
                    data={displaySources}
                    columns={sourceColumns}
                    getRowId={(r) => r.id}
                    selectedIds={selectedSourceIds}
                    scrollContainerRef={sourceScrollRef}
                    onDisplayRowOrder={onSourceDisplayRowOrder}
                    onRowClick={(r, e) => {
                      handleSourceRowClick(r, e);
                      setSelectedLibraryId(null);
                    }}
                    emptyMessage="No source tracks (check API, DL, or match filters)."
                  />
                </SourceTopMatchContext.Provider>
              ) : (
                <DataTable<LibraryTrack>
                  data={libraryRows}
                  columns={libraryColumns}
                  getRowId={(r) => r.id}
                  selectedId={selectedLibraryId}
                  onRowClick={(r) => {
                    setSelectedLibraryId(r.id);
                    setSelectedSourceIds([]);
                  }}
                  emptyMessage="No library tracks."
                  enableSorting={false}
                  onNearEnd={libraryQuery.loadMore}
                  hasMore={libraryQuery.hasMore}
                  isLoadingMore={libraryQuery.isLoadingMore}
                />
              )}
            </div>
          </div>
        }
        secondary={
          <SecondaryPanel
            mainView={mainView}
            selectedSource={selectedSource}
            selectedLibrary={selectedLibrary}
            sourceSelectionCount={sourceSelectionCount}
            selectedSourcesBulk={selectedSourcesBulk}
            candidates={matchCandidates.data}
            candidatesLoading={matchCandidates.isLoading}
            candidatesError={matchCandidates.error}
            matchActionBusy={matchActionBusy}
            onPickSelectedMatches={runPickSelectedMatches}
            onRejectSelectedMatches={runRejectSelectedMatches}
            onPickCandidate={(c: MatchCandidate) => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () =>
                matchPick(sid, c.id, c.match_score),
              );
            }}
            onPickTopMatch={() => {
              const s = selectedSource;
              if (!s) return;
              const lid = s.top_match_library_track_id;
              const sc = s.top_match_score;
              if (lid == null || sc == null) return;
              void withMatchActionForSource(s.id, () =>
                matchPick(s.id, lid, sc),
              );
            }}
            onRejectNoMatch={() => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () => matchReject(sid));
            }}
            onUndoPick={() => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () => matchUndoPick(sid));
            }}
            onUndoReject={() => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () => matchUndoReject(sid));
            }}
          />
        }
      />
    </AppShell>
  );
}
