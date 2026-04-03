import { useEffect, useMemo, useState } from "react";

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

  const candidates = useMatchCandidates(
    mainView === "sources" ? selectedSource : null,
    libraryQuery.data,
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
    mainView === "sources" ? sourceQuery.isLoading : libraryQuery.isLoading;

  return (
    <AppShell>
      <WorkspaceLayout
        toolbar={
          <div className="flex flex-wrap items-center gap-3">
            <MainViewTabs value={mainView} onChange={setMainView} />
            {mainView === "sources" ? (
              <DlFilterSelect value={dlFilter} onChange={setDlFilter} />
            ) : null}
          </div>
        }
        primary={
          <div className="flex min-h-0 flex-1 flex-col gap-1">
            <h2 className="shrink-0 text-[0.7rem] font-semibold uppercase tracking-wide text-muted">
              {mainView === "sources" ? "Source tracks" : "Library tracks"}
            </h2>
            <div className="min-h-0 flex-1 overflow-hidden">
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
            candidates={candidates}
          />
        }
      />
    </AppShell>
  );
}
