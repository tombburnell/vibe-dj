import { useEffect, useMemo, useRef, useState } from "react";

import {
  importLibrarySnapshot,
  importPlaylistCsv,
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
import { SecondaryPanel } from "@/components/workspace/SecondaryPanel";
import { useLibraryTracks } from "@/hooks/useLibraryTracks";
import { useMatchCandidates } from "@/hooks/useMatchCandidates";
import { useSourceTracks } from "@/hooks/useSourceTracks";
import { useToast } from "@/providers/ToastProvider";

export function WorkspacePage() {
  const { showToast } = useToast();
  const sourceQuery = useSourceTracks();
  const libraryQuery = useLibraryTracks();
  const [mainView, setMainView] = useState<MainView>("sources");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [selectedLibraryId, setSelectedLibraryId] = useState<string | null>(null);
  const [dlFilter, setDlFilter] = useState<DlFilter>("all");
  const [playlistName, setPlaylistName] = useState("Imported playlist");
  const libraryFileRef = useRef<HTMLInputElement>(null);
  const playlistFileRef = useRef<HTMLInputElement>(null);

  const sourceColumns = useMemo(() => buildSourceTrackColumns(), []);
  const libraryColumns = useMemo(() => buildLibraryTrackColumns(), []);

  const filteredSources = useMemo(() => {
    const rows = sourceQuery.data ?? [];
    if (dlFilter === "downloaded") return rows.filter((s) => Boolean(s.local_file_path));
    if (dlFilter === "not_downloaded") return rows.filter((s) => !s.local_file_path);
    return rows;
  }, [sourceQuery.data, dlFilter]);

  const selectedSource = useMemo(
    () => filteredSources.find((s) => s.id === selectedSourceId) ?? null,
    [filteredSources, selectedSourceId],
  );

  const libraryRows = libraryQuery.data ?? [];
  const selectedLibrary = useMemo(
    () => libraryRows.find((l) => l.id === selectedLibraryId) ?? null,
    [libraryRows, selectedLibraryId],
  );

  const matchCandidates = useMatchCandidates(
    mainView === "sources" ? selectedSource : null,
  );

  useEffect(() => {
    if (sourceQuery.error) showToast(sourceQuery.error.message, "error");
  }, [sourceQuery.error, showToast]);

  useEffect(() => {
    if (libraryQuery.error) showToast(libraryQuery.error.message, "error");
  }, [libraryQuery.error, showToast]);

  useEffect(() => {
    if (selectedSourceId && !filteredSources.some((s) => s.id === selectedSourceId)) {
      setSelectedSourceId(null);
    }
  }, [filteredSources, selectedSourceId]);

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
              <DlFilterSelect value={dlFilter} onChange={setDlFilter} />
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
                const name = playlistName.trim() || "Imported playlist";
                try {
                  const r = await importPlaylistCsv(f, name);
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
            <input
              type="text"
              value={playlistName}
              onChange={(e) => setPlaylistName(e.target.value)}
              placeholder="Playlist name"
              className="w-40 rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary placeholder:text-muted"
              aria-label="Playlist name for CSV import"
            />
            <button
              type="button"
              className="rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-1"
              onClick={() => playlistFileRef.current?.click()}
            >
              Import playlist CSV
            </button>
            <button
              type="button"
              className="rounded border border-border bg-surface-2 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-1"
              onClick={async () => {
                try {
                  const r = await runMatchJob({});
                  showToast(
                    `Match: ${r.matched_count} auto-linked, ${r.skipped_count} skipped`,
                    "info",
                  );
                  sourceQuery.refetch();
                } catch (err) {
                  showToast(err instanceof Error ? err.message : String(err), "error");
                }
              }}
            >
              Run matching
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
                <TableSkeleton rows={10} cols={5} />
              ) : mainView === "sources" ? (
                <DataTable<SourceTrack>
                  data={filteredSources}
                  columns={sourceColumns}
                  getRowId={(r) => r.id}
                  selectedId={selectedSourceId}
                  onRowClick={(r) => {
                    setSelectedSourceId(r.id);
                    setSelectedLibraryId(null);
                  }}
                  emptyMessage="No source tracks (check API or DL filter)."
                />
              ) : (
                <DataTable<LibraryTrack>
                  data={libraryRows}
                  columns={libraryColumns}
                  getRowId={(r) => r.id}
                  selectedId={selectedLibraryId}
                  onRowClick={(r) => {
                    setSelectedLibraryId(r.id);
                    setSelectedSourceId(null);
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
            candidates={matchCandidates.data}
            candidatesLoading={matchCandidates.isLoading}
            candidatesError={matchCandidates.error}
          />
        }
      />
    </AppShell>
  );
}
