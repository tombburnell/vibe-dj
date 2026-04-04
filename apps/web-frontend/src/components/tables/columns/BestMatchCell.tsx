import type { Row } from "@tanstack/react-table";

import type { SourceTrack } from "@/api/types";
import { useSourceTopMatchLoading } from "@/contexts/SourceTopMatchContext";
import { formatDurationMs } from "@/lib/formatDuration";

type DurationDeviation = { className: string; title?: string };

/** Relative length difference vs source; red >30%, orange >10%, else muted. */
function topMatchDurationDeviation(
  sourceMs: number | null | undefined,
  matchMs: number | null | undefined,
): DurationDeviation {
  if (sourceMs == null || matchMs == null || sourceMs <= 0) {
    return { className: "text-muted" };
  }
  const rel = Math.abs(matchMs - sourceMs) / sourceMs;
  if (rel > 0.3) {
    return {
      className: "text-red-500",
      title: `Source ${formatDurationMs(sourceMs)} — ${Math.round(rel * 100)}% length difference`,
    };
  }
  if (rel > 0.1) {
    return {
      className: "text-orange-500",
      title: `Source ${formatDurationMs(sourceMs)} — ${Math.round(rel * 100)}% length difference`,
    };
  }
  return { className: "text-muted" };
}

export function BestMatchCell({ row }: { row: Row<SourceTrack> }) {
  const { isTopMatchLoading } = useSourceTopMatchLoading();
  const busy = isTopMatchLoading(row.original.id);
  const t = row.original.top_match_title;
  const a = row.original.top_match_artist;
  const s = row.original.top_match_score;
  const dur = row.original.top_match_duration_ms;
  const sourceDur = row.original.duration_ms;
  const picked = row.original.top_match_is_picked === true;
  const rejected = row.original.is_rejected_no_match === true;
  if (busy) {
    return (
      <div
        className="flex min-w-0 flex-col gap-1 py-px leading-none"
        aria-busy="true"
        aria-label="Loading best match"
      >
        <div className="flex min-w-0 gap-1.5">
          <div className="best-match-skeleton-glow h-2.5 min-w-0 flex-1 rounded bg-surface-2/90" />
          <div className="best-match-skeleton-glow h-2.5 w-7 shrink-0 rounded bg-surface-2/90" />
        </div>
        <div className="best-match-skeleton-glow h-2 w-[70%] max-w-[8rem] rounded bg-surface-2/75" />
      </div>
    );
  }

  if (rejected) {
    return (
      <span
        className="inline-flex min-w-0 max-w-full items-center gap-1.5 text-[length:var(--text-src-triple,0.8125rem)] leading-none text-muted"
        title="Missing — not in library"
      >
        <svg
          className="size-[1.1em] shrink-0 opacity-90"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M12 5v10" />
          <path d="m7 10 5 5 5-5" />
          <path d="M5 19h14" />
        </svg>
        <span className="min-w-0 font-medium">Missing</span>
      </span>
    );
  }

  if (row.original.top_match_below_minimum === true) {
    return (
      <span className="text-[0.55rem] leading-tight text-muted">
        Minimum score not met
      </span>
    );
  }

  if (t == null && s == null) {
    return (
      <span className="text-[0.55rem] leading-none text-muted">—</span>
    );
  }

  const durationDev = topMatchDurationDeviation(sourceDur, dur);

  return (
    <div className="flex min-w-0 flex-col gap-px leading-none">
      <div className="flex min-w-0 items-baseline gap-1.5 text-[0.7rem] leading-[1.2]">
        {picked ? (
          <span className="shrink-0 text-emerald-500" title="Manually matched">
            ✓
          </span>
        ) : null}
        <span className="min-w-0 flex-1 truncate text-primary">
          {t ?? "—"}
        </span>
      </div>
      <div className="flex min-w-0 items-baseline gap-1 text-[0.625rem] leading-[1.2]">
        {dur != null ? (
          <>
            <span
              className={`shrink-0 tabular-nums ${durationDev.className}`}
              title={durationDev.title}
            >
              {formatDurationMs(dur)}
            </span>
            <span className="shrink-0 text-muted">·</span>
          </>
        ) : null}
        <span className="min-w-0 truncate text-secondary">{a ?? "—"}</span>
      </div>
    </div>
  );
}
