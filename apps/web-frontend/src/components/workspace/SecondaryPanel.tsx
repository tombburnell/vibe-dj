import type { LibraryTrack } from "@/api/types";
import type { MatchCandidate } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import type { MainView } from "./MainViewTabs";

type Props = {
  mainView: MainView;
  /** Single-row focus (exactly one source selected). */
  selectedSource: SourceTrack | null;
  selectedLibrary: LibraryTrack | null;
  /** Number of selected source rows (0 / 1 / many). */
  sourceSelectionCount: number;
  /** Merged rows for current multi-selection (length ≥ 2 when bulk UI). */
  selectedSourcesBulk: SourceTrack[];
  candidates: MatchCandidate[];
  candidatesLoading: boolean;
  candidatesError: Error | null;
  matchActionBusy: boolean;
  onPickCandidate: (c: MatchCandidate) => void | Promise<void>;
  onRejectNoMatch: () => void | Promise<void>;
  onUndoPick: () => void | Promise<void>;
  onUndoAuto: () => void | Promise<void>;
  onUndoReject: () => void | Promise<void>;
  onPickSelectedMatches: () => void | Promise<void>;
  onRejectSelectedMatches: () => void | Promise<void>;
};

export function SecondaryPanel({
  mainView,
  selectedSource,
  selectedLibrary,
  sourceSelectionCount,
  selectedSourcesBulk,
  candidates,
  candidatesLoading,
  candidatesError,
  matchActionBusy,
  onPickCandidate,
  onRejectNoMatch,
  onUndoPick,
  onUndoAuto,
  onUndoReject,
  onPickSelectedMatches,
  onRejectSelectedMatches,
}: Props) {
  if (mainView === "sources") {
    if (sourceSelectionCount === 0) {
      return (
        <PanelChrome title="Matches">
          <p className="text-[var(--text-table)] text-muted">
            Select source row(s). Use Ctrl/Cmd+click to add rows; Shift+click for a range. One row:
            current match and candidates. Several rows: bulk actions.
          </p>
        </PanelChrome>
      );
    }

    if (sourceSelectionCount > 1) {
      const pickable = selectedSourcesBulk.filter(
        (s) =>
          s.top_match_library_track_id != null &&
          s.top_match_score != null &&
          !s.is_rejected_no_match &&
          !s.top_match_is_picked,
      );
      return (
        <PanelChrome title="Matches">
          <p className="mb-2 text-[0.7rem] text-muted">
            {sourceSelectionCount} tracks selected
          </p>
          <p className="mb-3 text-[0.7rem] text-[var(--text-table)] text-secondary">
            Pick applies each row&apos;s current best match (from the table). Rows without a match,
            rejected, or already picked are skipped.
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              disabled={matchActionBusy || pickable.length === 0}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() => void onPickSelectedMatches()}
            >
              Pick selected matches
              {pickable.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted">({pickable.length} eligible)</span>
              ) : null}
            </button>
            <button
              type="button"
              disabled={matchActionBusy}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() => void onRejectSelectedMatches()}
            >
              Reject selected matches
            </button>
          </div>
        </PanelChrome>
      );
    }

    if (!selectedSource) {
      return (
        <PanelChrome title="Matches">
          <p className="text-[var(--text-table)] text-muted">Loading selection…</p>
        </PanelChrome>
      );
    }

    const rejected = selectedSource.is_rejected_no_match === true;
    const picked = selectedSource.top_match_is_picked === true;
    const hasTop =
      selectedSource.top_match_title != null || selectedSource.top_match_score != null;
    const topId = selectedSource.top_match_library_track_id ?? null;
    const canUndoAuto = hasTop && !picked && !rejected;
    const candidatesVisible =
      topId == null ? candidates : candidates.filter((c) => c.id !== topId);

    return (
      <PanelChrome title="Matches">
        <p className="mb-2 text-[0.7rem] text-muted">
          {selectedSource.artist} — {selectedSource.title}
        </p>

        <div className="mb-3 space-y-2 rounded border border-border/70 bg-surface-2/50 px-2 py-2 text-[0.7rem] text-[var(--text-table)]">
          <div className="font-medium text-secondary">Current match</div>
          {rejected ? (
            <p className="text-muted">No match (rejected for this library scope).</p>
          ) : hasTop ? (
            <div>
              <div className="text-primary">
                {picked ? (
                  <span className="mr-1 text-emerald-500" title="Manually picked">
                    ✓
                  </span>
                ) : null}
                {selectedSource.top_match_title ?? "—"}
              </div>
              <div className="text-secondary">{selectedSource.top_match_artist ?? "—"}</div>
              {selectedSource.top_match_score != null ? (
                <div className="tabular-nums text-muted">
                  {Math.round(selectedSource.top_match_score * 100)}% ·{" "}
                  {formatDurationMs(selectedSource.top_match_duration_ms)}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-muted">No match yet (below min score or no library).</p>
          )}

          <div className="flex flex-wrap gap-1.5 pt-1">
            {!rejected ? (
              <button
                type="button"
                disabled={matchActionBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => void onRejectNoMatch()}
              >
                Reject (no match)
              </button>
            ) : (
              <button
                type="button"
                disabled={matchActionBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => void onUndoReject()}
              >
                Undo reject
              </button>
            )}
            {picked ? (
              <button
                type="button"
                disabled={matchActionBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => void onUndoPick()}
              >
                Undo pick
              </button>
            ) : null}
            {canUndoAuto ? (
              <button
                type="button"
                disabled={matchActionBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => void onUndoAuto()}
              >
                Unmatch
              </button>
            ) : null}
          </div>
        </div>

        <div className="text-[0.65rem] font-medium uppercase tracking-wide text-secondary">
          Candidates
        </div>
        {candidatesError ? (
          <p className="mt-1 text-[var(--text-table)] text-red-400">{candidatesError.message}</p>
        ) : candidatesLoading ? (
          <p className="mt-1 text-[var(--text-table)] text-muted">Loading candidates…</p>
        ) : candidatesVisible.length === 0 ? (
          <p className="mt-1 text-[var(--text-table)] text-muted">No candidates for this source.</p>
        ) : (
          <ul className="mt-1 space-y-1.5 text-[var(--text-table)]">
            {candidatesVisible.map((c) => {
              const isCurrent = topId != null && c.id === topId;
              return (
                <li
                  key={c.id}
                  className={`rounded border px-2 py-1 ${
                    isCurrent
                      ? "border-emerald-600/50 bg-emerald-950/20"
                      : "border-border/70 bg-surface-2/40"
                  }`}
                >
                  <div className="font-medium text-primary">{c.title}</div>
                  <div className="text-secondary">{c.artist}</div>
                  <div className="tabular-nums text-muted">
                    score {(c.match_score * 100).toFixed(0)}% ·{" "}
                    {formatDurationMs(c.duration_ms)} · {c.bpm != null ? `${c.bpm} BPM` : "—"} ·{" "}
                    {c.musical_key ?? "—"}
                  </div>
                  <button
                    type="button"
                    disabled={matchActionBusy || rejected}
                    className="mt-1 rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                    onClick={() => void onPickCandidate(c)}
                  >
                    Pick
                  </button>
                </li>
              );
            })}
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
