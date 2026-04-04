import type { LibraryTrack } from "@/api/types";
import type { MatchCandidate } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import type { MainView } from "./MainViewTabs";

/** 0–1 title/artist fuzzy quality from API; lower → orange / red on the line. */
function candidateComponentClass(
  score: number,
  role: "title" | "artist",
): string {
  if (score >= 0.72) {
    return role === "title" ? "font-medium text-primary" : "text-secondary";
  }
  if (score >= 0.45) {
    return role === "title" ? "font-medium text-orange-500" : "text-orange-500";
  }
  return role === "title" ? "font-medium text-red-500" : "text-red-500";
}

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
  onPickTopMatch: () => void | Promise<void>;
  onRejectNoMatch: () => void | Promise<void>;
  onUndoPick: () => void | Promise<void>;
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
  onPickTopMatch,
  onRejectNoMatch,
  onUndoPick,
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
          !s.top_match_is_picked &&
          !s.top_match_below_minimum,
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
    const belowMin = selectedSource.top_match_below_minimum === true;
    const hasTop =
      (selectedSource.top_match_title != null || selectedSource.top_match_score != null) &&
      !belowMin;
    const topId = selectedSource.top_match_library_track_id ?? null;
    const topScore = selectedSource.top_match_score;
    const canPickTop =
      hasTop &&
      !picked &&
      !rejected &&
      !belowMin &&
      topId != null &&
      topScore != null;
    const topSectionHeading = rejected
      ? "No match"
      : belowMin
        ? "Best match"
        : !hasTop
          ? "Best match"
          : picked
            ? "Current match"
            : "Top candidate";
    const candidatesVisible =
      topId == null ? candidates : candidates.filter((c) => c.id !== topId);

    return (
      <PanelChrome title="Matches">
        <p className="mb-2 text-[0.7rem] text-muted">
          {selectedSource.artist} — {selectedSource.title}
        </p>

        <div className="mb-3 space-y-2 rounded border border-border/70 bg-surface-2/50 px-2 py-2 text-[0.7rem] text-[var(--text-table)]">
          <div className="font-medium text-secondary">{topSectionHeading}</div>
          {rejected ? (
            <p className="text-muted">No match (rejected for this library scope).</p>
          ) : belowMin ? (
            <p className="text-[0.55rem] leading-tight text-muted">
              Minimum score not met
            </p>
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
              <>
                {canPickTop ? (
                  <button
                    type="button"
                    disabled={matchActionBusy}
                    className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                    onClick={() => void onPickTopMatch()}
                  >
                    Pick
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={matchActionBusy}
                  className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                  onClick={() => void onRejectNoMatch()}
                >
                  Reject (no match)
                </button>
              </>
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
          <ul className="mt-1 space-y-2">
            {candidatesVisible.map((c) => {
              const isCurrent = topId != null && c.id === topId;
              const titleS = c.title_match_score;
              const artistS = c.artist_match_score;
              return (
                <li
                  key={c.id}
                  className={`rounded-md border-0 px-2 py-1.5 text-[0.6rem] leading-snug ${
                    isCurrent
                      ? "bg-emerald-950/25 ring-1 ring-emerald-600/35 dark:bg-emerald-950/20"
                      : "bg-neutral-300/80 dark:bg-neutral-800/85"
                  }`}
                >
                  <div className="flex gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex min-w-0 flex-wrap items-baseline gap-x-1 gap-y-0">
                        <span
                          className={`min-w-0 flex-1 truncate ${candidateComponentClass(titleS, "title")}`}
                        >
                          {c.title}
                        </span>
                        <span className="shrink-0 italic tabular-nums text-muted">
                          {Math.round(titleS * 100)}%
                        </span>
                      </div>
                      <div className="mt-px flex min-w-0 flex-wrap items-baseline gap-x-1 gap-y-0">
                        <span
                          className={`min-w-0 flex-1 truncate ${candidateComponentClass(artistS, "artist")}`}
                        >
                          {c.artist}
                        </span>
                        <span className="shrink-0 italic tabular-nums text-muted">
                          {Math.round(artistS * 100)}%
                        </span>
                      </div>
                      <div className="mt-1 tabular-nums text-[0.52rem] text-muted">
                        {formatDurationMs(c.duration_ms)} ·{" "}
                        {c.bpm != null ? `${c.bpm} BPM` : "—"} · {c.musical_key ?? "—"}
                      </div>
                      <button
                        type="button"
                        disabled={matchActionBusy || rejected}
                        className="mt-1 rounded border border-border/50 bg-surface-1 px-1.5 py-0.5 text-[0.58rem] text-primary hover:bg-surface-2 disabled:opacity-50 dark:bg-surface-2/80"
                        onClick={() => void onPickCandidate(c)}
                      >
                        Pick
                      </button>
                    </div>
                    <div className="shrink-0 self-start tabular-nums text-[0.68rem] font-semibold text-primary">
                      {Math.round(c.match_score * 100)}%
                    </div>
                  </div>
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
