import type { Row } from "@tanstack/react-table";

import type { SourceTrack } from "@/api/types";
import { useSourceTopMatchLoading } from "@/contexts/SourceTopMatchContext";

export function MatchScoreCell({ row }: { row: Row<SourceTrack> }) {
  const { isTopMatchLoading } = useSourceTopMatchLoading();
  const busy = isTopMatchLoading(row.original.id);
  const s = row.original.top_match_score;
  const rejected = row.original.is_rejected_no_match === true;

  if (busy) {
    return (
      <span
        className="best-match-skeleton-glow inline-block h-2.5 w-8 rounded bg-surface-2/90"
        aria-busy="true"
        aria-label="Loading score"
      />
    );
  }

  const sz = "text-[length:var(--text-src-triple)]";

  if (rejected) {
    return <span className={`${sz} text-muted`}>—</span>;
  }

  if (s == null || typeof s !== "number") {
    return <span className={`${sz} text-muted`}>—</span>;
  }

  return (
    <span className={`${sz} tabular-nums text-secondary`}>
      {Math.round(s * 100)}%
    </span>
  );
}
