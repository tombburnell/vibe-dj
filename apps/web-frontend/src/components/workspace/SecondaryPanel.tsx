import type { LibraryTrack } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import type { MainView } from "./MainViewTabs";

type Props = {
  mainView: MainView;
  selectedSource: SourceTrack | null;
  selectedLibrary: LibraryTrack | null;
  candidates: LibraryTrack[];
};

export function SecondaryPanel({
  mainView,
  selectedSource,
  selectedLibrary,
  candidates,
}: Props) {
  if (mainView === "sources") {
    if (!selectedSource) {
      return (
        <PanelChrome title="Matches">
          <p className="text-[var(--text-table)] text-muted">
            Select a source row to see ranked library candidates (demo heuristic until API
            exists).
          </p>
        </PanelChrome>
      );
    }
    return (
      <PanelChrome title="Match candidates">
        <p className="mb-2 text-[0.7rem] text-muted">
          {selectedSource.artist} — {selectedSource.title}
        </p>
        {candidates.length === 0 ? (
          <p className="text-[var(--text-table)] text-muted">No heuristic matches.</p>
        ) : (
          <ul className="space-y-1.5 text-[var(--text-table)]">
            {candidates.map((c) => (
              <li
                key={c.id}
                className="rounded border border-border/80 bg-surface-2 px-2 py-1"
              >
                <div className="font-medium text-primary">{c.title}</div>
                <div className="text-secondary">{c.artist}</div>
                <div className="tabular-nums text-muted">
                  {formatDurationMs(c.duration_ms)} · {c.bpm != null ? `${c.bpm} BPM` : "—"} ·{" "}
                  {c.musical_key ?? "—"}
                </div>
              </li>
            ))}
          </ul>
        )}
      </PanelChrome>
    );
  }

  if (!selectedLibrary) {
    return (
      <PanelChrome title="Details">
        <p className="text-[var(--text-table)] text-muted">
          Select a library row for path and metadata.
        </p>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Library file">
      <dl className="space-y-2 text-[var(--text-table)]">
        <div>
          <dt className="text-muted">Path</dt>
          <dd className="break-all font-mono text-[0.7rem] text-secondary">
            {selectedLibrary.file_path}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Track</dt>
          <dd className="text-primary">
            {selectedLibrary.artist} — {selectedLibrary.title}
          </dd>
        </div>
      </dl>
    </PanelChrome>
  );
}

function PanelChrome({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      className="flex h-full min-h-0 flex-col rounded border border-border bg-surface-1"
      aria-label={title}
    >
      <header className="border-b border-border bg-surface-2 px-2 py-1.5 text-[0.7rem] font-semibold uppercase tracking-wide text-secondary">
        {title}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-2">{children}</div>
    </section>
  );
}
