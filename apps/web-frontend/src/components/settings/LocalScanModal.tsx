import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { HiXMark } from "react-icons/hi2";

import type { LocalScanMatched, LocalScanResult, LocalScanUnmatched } from "@/api/types";
import { setSourceTrackLocalFile } from "@/api/endpoints";
import { useToast } from "@/providers/ToastProvider";

type Phase = "scanning" | "done" | "error";

type ScanResultsTab = "unmatched" | "newlyMatched" | "previouslyMatched";

type Props = {
  open: boolean;
  onClose: () => void;
  phase: Phase;
  totalAudioFiles: number;
  progress: { chunkIndex: number; chunkCount: number } | null;
  result: LocalScanResult | null;
  error: string | null;
  onUnmatchedManuallyMatched?: (row: LocalScanMatched) => void;
};

function trackFileName(path: string): string {
  const n = path.replace(/\\/g, "/").split("/").pop();
  return n?.length ? n : path;
}

function buildUnmatchedList(result: LocalScanResult): LocalScanUnmatched[] {
  if (result.unmatched_details?.length) {
    return result.unmatched_details;
  }
  return result.unmatched_files.map((path) => ({
    path,
    parsed_artist: null,
    parsed_title: null,
    best_score: 0,
    best_source_track_id: null,
    best_source_artist: null,
    best_source_title: null,
    below_threshold: true,
    source_claimed_by_other_file: false,
    best_source_already_has_file: false,
  }));
}

function unmatchedExplanation(u: LocalScanUnmatched, minScore: number): string {
  if (!u.parsed_title?.trim()) {
    return 'Could not parse a title from the filename. Use "Artist - Title" before the extension.';
  }
  if (u.best_source_already_has_file && u.best_source_artist != null) {
    return `Best match ${u.best_source_artist} — ${u.best_source_title} (${u.best_score.toFixed(1)}%). That source row already has a local file path, so it was not in the auto-match pool. Clear the path in the workspace (DL column) or use Match here to replace it with this file.`;
  }
  if (u.source_claimed_by_other_file && u.best_source_artist != null) {
    return `Closest source (${u.best_score.toFixed(1)}%): ${u.best_source_artist} — ${u.best_source_title}. That row was already matched to another file in this scan.`;
  }
  if (u.below_threshold) {
    const closest =
      u.best_source_artist != null
        ? `${u.best_source_artist} — ${u.best_source_title} (${u.best_score.toFixed(1)}%)`
        : `${u.best_score.toFixed(1)}%`;
    return `Best match ${closest}; needs ≥ ${minScore.toFixed(0)}%. Parsed from file: ${u.parsed_artist ?? "—"} — ${u.parsed_title}. (Only the first " - " splits artist vs title—extra " - " in the filename often hurts remixes.)`;
  }
  return `Not matched (best score ${u.best_score.toFixed(1)}%).`;
}

function bestMatchHeadline(u: LocalScanUnmatched): string {
  if (u.best_source_artist != null && u.best_source_title != null) {
    return `${u.best_source_artist} — ${u.best_source_title} (${u.best_score.toFixed(1)}%)`;
  }
  if (u.best_score > 0) {
    return `${u.best_score.toFixed(1)}% (no source row identified)`;
  }
  return "No close match";
}

function UnmatchedRowsTable({
  rows,
  minScore,
  matchingPath,
  onMatchClick,
}: {
  rows: LocalScanUnmatched[];
  minScore: number;
  matchingPath: string | null;
  onMatchClick: (u: LocalScanUnmatched) => void;
}) {
  if (rows.length === 0) {
    return (
      <p className="text-[0.75rem] text-muted">No tracks in this list.</p>
    );
  }
  return (
    <div className="max-h-full overflow-auto rounded border border-border">
      <div className="divide-y divide-border">
        <div className="sticky top-0 z-10 grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] gap-2 bg-surface-2 px-2 py-1.5 text-[0.65rem] font-medium text-muted">
          <div>Track filename</div>
          <div>Best match details</div>
          <div className="text-right" />
        </div>
        {rows.map((u) => (
          <div
            key={u.path}
            className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] items-start gap-2 px-2 py-2 text-[0.7rem]"
          >
            <div className="min-w-0">
              <div className="break-all font-medium text-primary">
                {trackFileName(u.path)}
              </div>
              <div className="mt-0.5 break-all text-[0.65rem] text-muted">{u.path}</div>
            </div>
            <div className="min-w-0 text-secondary">
              <div className="text-primary">{bestMatchHeadline(u)}</div>
              <div className="mt-1 text-[0.65rem] text-muted">
                {unmatchedExplanation(u, minScore)}
              </div>
            </div>
            <div className="flex justify-end pt-0.5">
              <button
                type="button"
                disabled={!u.best_source_track_id || matchingPath === u.path}
                title={
                  u.best_source_track_id
                    ? "Link this file to the best-matching source row"
                    : "No source row to link"
                }
                className="whitespace-nowrap rounded border border-border bg-surface-2 px-2 py-1 text-[0.7rem] text-primary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => onMatchClick(u)}
              >
                {matchingPath === u.path ? "…" : "Match"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NewlyMatchedTable({ rows }: { rows: LocalScanMatched[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-[0.75rem] text-muted">No tracks were auto-matched in this scan.</p>
    );
  }
  return (
    <div className="max-h-full overflow-auto rounded border border-border">
      <div className="divide-y divide-border">
        <div className="sticky top-0 z-10 grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_auto] gap-2 bg-surface-2 px-2 py-1.5 text-[0.65rem] font-medium text-muted">
          <div>File path</div>
          <div>Source track</div>
          <div className="text-right tabular-nums">Score</div>
        </div>
        {rows.map((m) => (
          <div
            key={`${m.source_track_id}-${m.path}`}
            className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_auto] gap-2 px-2 py-1.5 text-[0.7rem]"
          >
            <div className="break-all text-primary">{m.path}</div>
            <div className="text-secondary">
              <span className="text-primary">{m.artist}</span>
              {" — "}
              <span>{m.title}</span>
            </div>
            <div className="text-right tabular-nums text-muted">{m.score.toFixed(1)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LocalScanModal({
  open,
  onClose,
  phase,
  totalAudioFiles,
  progress,
  result,
  error,
  onUnmatchedManuallyMatched,
}: Props) {
  const titleId = useId();
  const { showToast } = useToast();
  const [matchingPath, setMatchingPath] = useState<string | null>(null);
  const [resultsTab, setResultsTab] = useState<ScanResultsTab>("unmatched");
  const prevPhaseRef = useRef<Phase>(phase);

  useEffect(() => {
    if (prevPhaseRef.current === "scanning" && phase === "done") {
      setResultsTab("unmatched");
    }
    prevPhaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      console.info("[local-scan]", "LocalScanModal portal render", {
        phase,
        totalAudioFiles,
      });
    }
  }, [open, phase, totalAudioFiles]);

  useEffect(() => {
    if (!open) setMatchingPath(null);
  }, [open]);

  if (!open) return null;
  if (typeof document === "undefined") return null;

  const pct =
    progress && progress.chunkCount > 0
      ? Math.round((progress.chunkIndex / progress.chunkCount) * 100)
      : 0;

  const minScore = result?.min_score ?? 80;

  const allUnmatched = result ? buildUnmatchedList(result) : [];
  const stillUnmatched = allUnmatched.filter((u) => !u.best_source_already_has_file);
  const previouslyMatched = allUnmatched.filter((u) => u.best_source_already_has_file);
  const newlyMatchedCount = result?.matched.length ?? 0;

  async function onMatchClick(u: LocalScanUnmatched) {
    const sid = u.best_source_track_id;
    if (!sid) return;
    setMatchingPath(u.path);
    try {
      const out = await setSourceTrackLocalFile(sid, u.path);
      onUnmatchedManuallyMatched?.({
        source_track_id: out.source_track_id,
        path: out.path,
        score: u.best_score,
        title: out.title,
        artist: out.artist,
      });
      showToast("Linked file to source track", "info");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(msg, "error");
    } finally {
      setMatchingPath(null);
    }
  }

  function tabClass(id: ScanResultsTab) {
    const on = resultsTab === id;
    return [
      "rounded-t px-3 py-2 text-[0.75rem] font-medium transition-colors",
      on
        ? "border border-b-0 border-border bg-surface-1 text-primary"
        : "border border-transparent text-muted hover:bg-surface-2 hover:text-secondary",
    ].join(" ");
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex h-[80vh] w-[80vw] max-h-[92vh] max-w-[95vw] flex-col overflow-hidden rounded-lg border border-border bg-surface-1 shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-[0.9rem] font-semibold text-primary">
              {phase === "scanning" && "Scanning folder"}
              {phase === "done" && "Local scan results"}
              {phase === "error" && "Scan failed"}
            </h2>
            {phase === "scanning" && (
              <p className="mt-1 text-[0.75rem] text-muted">
                Matching {totalAudioFiles} audio file{totalAudioFiles === 1 ? "" : "s"} to source
                tracks (paths only—no file contents uploaded).
              </p>
            )}
          </div>
          <button
            type="button"
            className="shrink-0 rounded p-1.5 text-muted hover:bg-surface-2 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label={phase === "scanning" ? "Cancel scan" : "Close"}
            onClick={onClose}
          >
            <HiXMark className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div
          className={
            phase === "done"
              ? "flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-3"
              : "min-h-0 flex-1 overflow-y-auto px-4 py-3"
          }
        >
          {phase === "scanning" && (
            <div className="space-y-3">
              <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full bg-accent transition-[width] duration-200"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-[0.75rem] text-secondary">
                {progress
                  ? `Sending batch ${progress.chunkIndex} of ${progress.chunkCount} to the server…`
                  : "Preparing…"}
              </p>
              <div
                className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent"
                aria-hidden
              />
            </div>
          )}

          {phase === "error" && error && (
            <p className="text-[0.8125rem] text-red-400">{error}</p>
          )}

          {phase === "done" && result && (
            <div className="flex min-h-0 flex-1 flex-col gap-3 text-[0.75rem]">
              <p className="shrink-0 text-secondary">
                <span className="font-medium text-primary">{newlyMatchedCount}</span> newly matched
                in this scan,{" "}
                <span className="font-medium text-primary">{stillUnmatched.length}</span> still
                unmatched,{" "}
                <span className="font-medium text-primary">{previouslyMatched.length}</span> skipped
                (source already had a local path),{" "}
                <span className="font-medium text-primary">{result.skipped_non_audio}</span> non-audio
                skipped
                {typeof result.min_score === "number" ? (
                  <>
                    {" "}
                    (min score <span className="tabular-nums">{result.min_score}</span>)
                  </>
                ) : null}
                .
              </p>

              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div
                  role="tablist"
                  aria-label="Scan result categories"
                  className="flex shrink-0 flex-wrap gap-0.5 border-b border-border"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={resultsTab === "unmatched"}
                    id="local-scan-tab-unmatched"
                    className={tabClass("unmatched")}
                    onClick={() => setResultsTab("unmatched")}
                  >
                    Unmatched
                    <span className="ml-1 tabular-nums text-muted">({stillUnmatched.length})</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={resultsTab === "newlyMatched"}
                    id="local-scan-tab-newly"
                    className={tabClass("newlyMatched")}
                    onClick={() => setResultsTab("newlyMatched")}
                  >
                    Newly matched
                    <span className="ml-1 tabular-nums text-muted">({newlyMatchedCount})</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={resultsTab === "previouslyMatched"}
                    id="local-scan-tab-prev"
                    className={tabClass("previouslyMatched")}
                    onClick={() => setResultsTab("previouslyMatched")}
                  >
                    Previously matched
                    <span className="ml-1 tabular-nums text-muted">
                      ({previouslyMatched.length})
                    </span>
                  </button>
                </div>

                <div
                  role="tabpanel"
                  aria-labelledby={
                    resultsTab === "unmatched"
                      ? "local-scan-tab-unmatched"
                      : resultsTab === "newlyMatched"
                        ? "local-scan-tab-newly"
                        : "local-scan-tab-prev"
                  }
                  className="min-h-0 flex-1 overflow-y-auto pt-3"
                >
                  {resultsTab === "unmatched" && (
                    <UnmatchedRowsTable
                      rows={stillUnmatched}
                      minScore={minScore}
                      matchingPath={matchingPath}
                      onMatchClick={(u) => void onMatchClick(u)}
                    />
                  )}
                  {resultsTab === "newlyMatched" && (
                    <NewlyMatchedTable rows={result.matched} />
                  )}
                  {resultsTab === "previouslyMatched" && (
                    <div className="space-y-2">
                      <p className="text-[0.7rem] text-muted">
                        These files line up with a source row that already has a local path. Use
                        Match to replace that path, or clear it from the workspace first.
                      </p>
                      <UnmatchedRowsTable
                        rows={previouslyMatched}
                        minScore={minScore}
                        matchingPath={matchingPath}
                        onMatchClick={(u) => void onMatchClick(u)}
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
