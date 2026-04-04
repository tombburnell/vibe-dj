import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";

import { queryKeys } from "@/api/queryKeys";
import type { MatchCandidate } from "@/api/types";
import {
  findAmazonLinks,
  importLibrarySnapshot,
  importPlaylistCsv,
  matchPick,
  matchReject,
  matchRejectBatch,
  matchUndoPick,
  matchUndoReject,
  postSourceTopMatches,
  runMatchJob,
  sourceWishlistBatch,
} from "@/api/endpoints";
import type { LibraryTrack } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import { AppShell } from "@/components/layout/AppShell";
import { WorkspaceLayout } from "@/components/layout/WorkspaceLayout";
import { DataTable } from "@/components/tables/DataTable";
import { buildDownloadTrackColumns } from "@/components/tables/columns/downloadTrackColumns";
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

const TOP_MATCH_BATCH_STALE_MS = 5 * 60 * 1000;

export function WorkspacePage() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [minMatchScore, setMinMatchScore] = useState(0.4);
  const sourceQuery = useSourceTracks(minMatchScore);
  const libraryQuery = useLibraryTracks();
  const [mainView, setMainView] = useState<MainView>("sources");
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedLibraryId, setSelectedLibraryId] = useState<string | null>(null);
  const [dlFilter, setDlFilter] = useState<DlFilter>("all");
  const [matchCategoryFilter, setMatchCategoryFilter] =
    useState<SourceMatchCategoryFilterState>(defaultSourceMatchCategoryFilter);
  const [topMatchEpoch, setTopMatchEpoch] = useState(0);
  const [matchActionBusy, setMatchActionBusy] = useState(false);
  const [runMatchingBusy, setRunMatchingBusy] = useState(false);
  const [findLinksBusy, setFindLinksBusy] = useState(false);
  const libraryFileRef = useRef<HTMLInputElement>(null);
  const playlistFileRef = useRef<HTMLInputElement>(null);
  const sourceScrollRef = useRef<HTMLDivElement>(null);
  const mergedSourcesRef = useRef<SourceTrack[]>([]);
  const sourceDisplayOrderRef = useRef<string[]>([]);
  const sourceShiftAnchorRef = useRef<string | null>(null);

  const onSourceDisplayRowOrder = useCallback((ids: string[]) => {
    sourceDisplayOrderRef.current = ids;
  }, []);

  const sourceColumns = useMemo(() => buildSourceTrackColumns(), []);
  const downloadColumns = useMemo(() => buildDownloadTrackColumns(), []);
  const libraryColumns = useMemo(() => buildLibraryTrackColumns(), []);

  const filteredSources = useMemo(() => {
    const rows = sourceQuery.data ?? [];
    let base = rows;
    if (dlFilter === "downloaded") base = base.filter((s) => Boolean(s.local_file_path));
    else if (dlFilter === "not_downloaded")
      base = base.filter((s) => !s.local_file_path);
    return base;
  }, [sourceQuery.data, dlFilter]);

  const listFingerprint = useMemo(
    () =>
      `${topMatchEpoch}:${minMatchScore}:${filteredSources.map((s) => s.id).sort().join(",")}`,
    [filteredSources, topMatchEpoch, minMatchScore],
  );

  const { overlay, loadingIds, applyTopMatchRows } = useVisibleSourceTopMatches(
    sourceScrollRef,
    (mainView === "sources" || mainView === "download") &&
      !sourceQuery.isLoading &&
      filteredSources.length > 0,
    listFingerprint,
    filteredSources.length,
    mergedSourcesRef,
    {
      onFetchError: (e) => showToast(e.message, "error"),
      minScore: minMatchScore,
      suspendAutoFetch: runMatchingBusy || findLinksBusy,
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
  mergedSourcesRef.current = mergedSources;

  const displaySources = useMemo(
    () => mergedSources.filter((s) => sourcePassesCategoryFilter(s, matchCategoryFilter)),
    [mergedSources, matchCategoryFilter],
  );

  const displayDownloadSources = useMemo(
    () =>
      mergedSources.filter(
        (s) => s.is_rejected_no_match === true && s.on_wishlist,
      ),
    [mergedSources],
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
  );

  const bumpMatchData = useCallback(() => {
    setTopMatchEpoch((e) => e + 1);
    void queryClient.invalidateQueries({ queryKey: queryKeys.matchCandidatesRoot });
  }, [queryClient]);

  const importLibraryMutation = useMutation({
    mutationFn: (file: File) => importLibrarySnapshot(file),
    onSuccess: (r) => {
      showToast(`Library import: ${r.track_count} tracks`, "info");
      void queryClient.invalidateQueries({ queryKey: queryKeys.libraryTracksInfinite });
      void queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      bumpMatchData();
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : String(err), "error");
    },
  });

  const importPlaylistMutation = useMutation({
    mutationFn: (file: File) => importPlaylistCsv(file),
    onSuccess: (r) => {
      showToast(
        `Playlist: linked ${r.rows_linked}, new sources ${r.new_source_tracks}`,
        "info",
      );
      void queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.playlists });
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : String(err), "error");
    },
  });

  const pickMatchMutation = useMutation({
    mutationFn: (args: {
      sourceTrackId: string;
      libraryTrackId: string;
      matchScore: number | null;
    }) => matchPick(args.sourceTrackId, args.libraryTrackId, args.matchScore),
  });

  const rejectMatchMutation = useMutation({
    mutationFn: (sourceTrackId: string) => matchReject(sourceTrackId),
  });

  const wishlistBatchMutation = useMutation({
    mutationFn: (args: { ids: string[]; onWishlist: boolean }) =>
      sourceWishlistBatch(
        [...new Set(args.ids)].filter(Boolean).slice(0, 100),
        args.onWishlist,
      ),
    onSuccess: (res, args) => {
      void queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      if (!args.onWishlist) {
        setSelectedSourceIds((prev) => prev.filter((id) => !args.ids.includes(id)));
      }
      showToast(
        `${args.onWishlist ? "Restored" : "Ignored"} ${res.updated_count} track(s).`,
        "info",
      );
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : String(err), "error");
    },
  });

  const undoPickMutation = useMutation({
    mutationFn: (sourceTrackId: string) => matchUndoPick(sourceTrackId),
  });

  const undoRejectMutation = useMutation({
    mutationFn: (sourceTrackId: string) => matchUndoReject(sourceTrackId),
  });

  const runMatchJobMutation = useMutation({
    mutationFn: () => runMatchJob({}),
  });

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
      const sortedUniq = [...uniq].sort();
      const rows = await queryClient.fetchQuery({
        queryKey: queryKeys.topMatchesBatch(minMatchScore, sortedUniq.join(",")),
        queryFn: () =>
          postSourceTopMatches(sortedUniq, { minScore: minMatchScore }),
        staleTime: TOP_MATCH_BATCH_STALE_MS,
      });
      applyTopMatchRows(rows);
      void queryClient.invalidateQueries({ queryKey: queryKeys.matchCandidatesRoot });
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
        "No eligible rows (need a best match ≥ min; skip rows already Need or matched).",
        "info",
      );
      return;
    }
    void withMatchActionForSources(selectedSourceIds, async () => {
      for (const s of targets) {
        await pickMatchMutation.mutateAsync({
          sourceTrackId: s.id,
          libraryTrackId: s.top_match_library_track_id!,
          matchScore: s.top_match_score,
        });
      }
      showToast(`Matched ${targets.length} track(s).`, "info");
    });
  };

  const runRejectSelectedMatches = () => {
    if (selectedSourceIds.length === 0) return;
    const ids = [...new Set(selectedSourceIds)].filter(Boolean).slice(0, 100);
    void withMatchActionForSources(ids, async () => {
      const { rejected_count: n } = await matchRejectBatch(ids);
      showToast(`Marked ${n} track(s) as Need.`, "info");
    });
  };

  const wishlistBusy = wishlistBatchMutation.isPending;

  const runWishlistForIds = (ids: string[], onWishlist: boolean) => {
    const u = [...new Set(ids)].filter(Boolean).slice(0, 100);
    if (u.length === 0) return;
    void wishlistBatchMutation.mutateAsync({ ids: u, onWishlist });
  };

  useEffect(() => {
    if (sourceQuery.error) showToast(sourceQuery.error.message, "error");
  }, [sourceQuery.error, showToast]);

  useEffect(() => {
    if (libraryQuery.error) showToast(libraryQuery.error.message, "error");
  }, [libraryQuery.error, showToast]);

  useEffect(() => {
    if (mainView === "library") {
      setSelectedSourceIds([]);
      return;
    }
    const visible =
      mainView === "download"
        ? new Set(displayDownloadSources.map((s) => s.id))
        : new Set(displaySources.map((s) => s.id));
    setSelectedSourceIds((prev) => prev.filter((id) => visible.has(id)));
  }, [mainView, displaySources, displayDownloadSources]);

  const primaryLoading =
    mainView === "library"
      ? libraryQuery.isLoading && libraryQuery.data.length === 0
      : sourceQuery.isLoading;

  const runFindLinksForDisplayed = () => {
    const ids = displayDownloadSources.map((s) => s.id);
    if (ids.length === 0) {
      showToast("No tracks in the Download queue.", "info");
      return;
    }
    setFindLinksBusy(true);
    void (async () => {
      try {
        const r = await findAmazonLinks({ source_track_ids: ids, force: false });
        showToast(
          `Find links: searched ${r.searched_count}, skipped cached ${r.skipped_cached_count}, errors ${r.error_count}`,
          "info",
        );
        void queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      } catch (err) {
        showToast(err instanceof Error ? err.message : String(err), "error");
      } finally {
        setFindLinksBusy(false);
      }
    })();
  };

  const runReSearchSelectedDownloads = () => {
    const ids = selectedSourceIds.filter((id) =>
      displayDownloadSources.some((s) => s.id === id),
    );
    if (ids.length === 0) {
      showToast("Select one or more Download rows to re-search.", "info");
      return;
    }
    setFindLinksBusy(true);
    void (async () => {
      try {
        const r = await findAmazonLinks({ source_track_ids: ids, force: true });
        showToast(
          `Re-search: searched ${r.searched_count}, errors ${r.error_count}`,
          "info",
        );
        void queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      } catch (err) {
        showToast(err instanceof Error ? err.message : String(err), "error");
      } finally {
        setFindLinksBusy(false);
      }
    })();
  };

  return (
    <AppShell
      headerMenuExtra={
        <>
          <input
            ref={libraryFileRef}
            type="file"
            accept=".tsv,text/tab-separated-values"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (!f) return;
              importLibraryMutation.mutate(f);
            }}
          />
          <button
            type="button"
            className="rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-2"
            onClick={() => libraryFileRef.current?.click()}
          >
            Import Rekordbox TSV
          </button>
          <input
            ref={playlistFileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (!f) return;
              importPlaylistMutation.mutate(f);
            }}
          />
          <button
            type="button"
            className="rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-2"
            onClick={() => playlistFileRef.current?.click()}
          >
            Import playlist CSV
          </button>
        </>
      }
    >
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
                      const r = await runMatchJobMutation.mutateAsync();
                      showToast(
                        `Match: ${r.matched_count} auto-linked, ${r.skipped_count} skipped`,
                        "info",
                      );
                      const rows = sourceQuery.data ?? [];
                      const ids = filterSourcesByDl(rows, dlFilter).map((s) => s.id);
                      for (let i = 0; i < ids.length; i += 100) {
                        const chunk = [...ids.slice(i, i + 100)].sort();
                        const sortedKey = chunk.join(",");
                        const batch = await queryClient.fetchQuery({
                          queryKey: queryKeys.topMatchesBatch(
                            minMatchScore,
                            sortedKey,
                          ),
                          queryFn: () =>
                            postSourceTopMatches(chunk, {
                              minScore: minMatchScore,
                            }),
                          staleTime: TOP_MATCH_BATCH_STALE_MS,
                        });
                        applyTopMatchRows(batch);
                      }
                      void queryClient.invalidateQueries({
                        queryKey: ["sourceTracks"],
                      });
                      void queryClient.invalidateQueries({
                        queryKey: queryKeys.matchCandidatesRoot,
                      });
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
              </>
            ) : mainView === "download" ? (
              <>
                <button
                  type="button"
                  disabled={findLinksBusy || displayDownloadSources.length === 0}
                  aria-busy={findLinksBusy}
                  className="inline-flex items-center gap-1.5 rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => runFindLinksForDisplayed()}
                >
                  {findLinksBusy ? (
                    <>
                      <span
                        className="inline-block size-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent opacity-80"
                        aria-hidden
                      />
                      <span>Finding…</span>
                    </>
                  ) : (
                    "Find links"
                  )}
                </button>
                <button
                  type="button"
                  disabled={
                    findLinksBusy ||
                    selectedSourceIds.filter((id) =>
                      displayDownloadSources.some((s) => s.id === id),
                    ).length === 0
                  }
                  className="rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => runReSearchSelectedDownloads()}
                >
                  Re-search selected
                </button>
              </>
            ) : null}
          </div>
        }
        primary={
          <div className="flex min-h-0 flex-1 flex-col gap-1">
            <h2 className="shrink-0 text-[0.7rem] font-semibold uppercase tracking-wide text-muted">
              {mainView === "sources"
                ? selectedSourceIds.length > 1
                  ? `SOURCE TRACKS (${selectedSourceIds.length} selected)`
                  : `SOURCE TRACKS (${displaySources.length}/${filteredSources.length})`
                : mainView === "download"
                  ? "Download queue"
                  : "Library tracks"}
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
              ) : mainView === "download" ? (
                <DataTable<SourceTrack>
                  data={displayDownloadSources}
                  columns={downloadColumns}
                  getRowId={(r) => r.id}
                  selectedIds={selectedSourceIds}
                  scrollContainerRef={sourceScrollRef}
                  onDisplayRowOrder={onSourceDisplayRowOrder}
                  onRowClick={(r, e) => {
                    handleSourceRowClick(r, e);
                    setSelectedLibraryId(null);
                  }}
                  emptyMessage='No Need tracks yet — in Sources, use "Need (no match)" on rows not in your library.'
                />
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
            wishlistBusy={wishlistBusy}
            findLinksBusy={findLinksBusy}
            onFindLinksDisplayed={runFindLinksForDisplayed}
            onReSearchSelectedDownloads={runReSearchSelectedDownloads}
            downloadQueueCount={displayDownloadSources.length}
            onPickSelectedMatches={runPickSelectedMatches}
            onRejectSelectedMatches={runRejectSelectedMatches}
            onPickCandidate={(c: MatchCandidate) => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () =>
                pickMatchMutation.mutateAsync({
                  sourceTrackId: sid,
                  libraryTrackId: c.id,
                  matchScore: c.match_score,
                }),
              );
            }}
            onPickTopMatch={() => {
              const s = selectedSource;
              if (!s) return;
              const lid = s.top_match_library_track_id;
              const sc = s.top_match_score;
              if (lid == null || sc == null) return;
              void withMatchActionForSource(s.id, () =>
                pickMatchMutation.mutateAsync({
                  sourceTrackId: s.id,
                  libraryTrackId: lid,
                  matchScore: sc,
                }),
              );
            }}
            onRejectNoMatch={() => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () =>
                rejectMatchMutation.mutateAsync(sid),
              );
            }}
            onUndoPick={() => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () =>
                undoPickMutation.mutateAsync(sid),
              );
            }}
            onUndoReject={() => {
              const sid = selectedSource?.id;
              if (!sid) return;
              void withMatchActionForSource(sid, () =>
                undoRejectMutation.mutateAsync(sid),
              );
            }}
            onWishlistSources={(ids, onWishlist) =>
              runWishlistForIds(ids, onWishlist)
            }
          />
        }
      />
    </AppShell>
  );
}
