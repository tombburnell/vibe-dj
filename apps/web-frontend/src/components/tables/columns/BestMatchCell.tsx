import type { Row } from "@tanstack/react-table";

import type { SourceTrack } from "@/api/types";
import { useSourceTopMatchLoading } from "@/contexts/SourceTopMatchContext";
import { formatDurationMs } from "@/lib/formatDuration";

export function BestMatchCell({ row }: { row: Row<SourceTrack> }) {
  const { isTopMatchLoading } = useSourceTopMatchLoading();
  const busy = isTopMatchLoading(row.original.id);
  const t = row.original.top_match_title;
  const a = row.original.top_match_artist;
  const s = row.original.top_match_score;
  const dur = row.original.top_match_duration_ms;
  const picked = row.original.top_match_is_picked === true;
  const rejected = row.original.is_rejected_no_match === true;

  if (busy) {
    return (
      <div
        className="flex min-w-0 flex-col gap-px leading-none"
        aria-busy="true"
        aria-label="Loading best match"
      >
        <div className="flex min-w-0 gap-1.5">
          <div className="h-2.5 min-w-0 flex-1 animate-pulse rounded bg-muted/35" />
          <div className="h-2.5 w-7 shrink-0 animate-pulse rounded bg-muted/35" />
        </div>
        <div className="h-2 w-[70%] max-w-[8rem] animate-pulse rounded bg-muted/25" />
      </div>
    );
  }

  if (rejected) {
    return (
      <span className="text-[0.55rem] leading-none text-muted">No match (rejected)</span>
    );
  }

  if (t == null && s == null) {
    return (
      <span className="text-[0.55rem] leading-none text-muted">—</span>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-px leading-none">
      <div className="flex min-w-0 items-baseline gap-1.5 text-[0.7rem] leading-[1.2]">
        {picked ? (
          <span className="shrink-0 text-emerald-500" title="Manually picked">
            ✓
          </span>
        ) : null}
        <span className="min-w-0 flex-1 truncate text-primary">
          {t ?? "—"}
        </span>
      </div>
      <div className="text-[0.5rem] leading-[1.15] text-secondary">
        <span className="truncate">
          {a ?? "—"}
          {dur != null ? (
            <span className="tabular-nums text-muted">
              {" "}
              · {formatDurationMs(dur)}
            </span>
          ) : null}
        </span>
      </div>
    </div>
  );
}
