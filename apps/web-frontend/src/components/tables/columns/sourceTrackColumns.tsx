import type { ColumnDef } from "@tanstack/react-table";

import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import { BestMatchCell } from "./BestMatchCell";
import { DownloadedCell } from "./DownloadedCell";
import { MatchScoreCell } from "./MatchScoreCell";
import { SortableHeader } from "../SortableHeader";

const PLAYLIST_CHIP_CHARS = 12;
/** Scales with density via --text-src-triple on parent td; chip ~same ratio as table. */
const PLAYLIST_CHIP_TEXT =
  "text-[length:calc(var(--text-src-triple,0.8125rem)*0.66)] leading-tight";

function playlistChipLabel(name: string): string {
  const t = name.trim();
  if (t.length <= PLAYLIST_CHIP_CHARS) return t;
  return `${t.slice(0, PLAYLIST_CHIP_CHARS)}…`;
}

export function buildSourceTrackColumns(): ColumnDef<SourceTrack>[] {
  return [
    {
      accessorKey: "title",
      size: 108,
      minSize: 72,
      maxSize: 560,
      header: ({ column }) => <SortableHeader column={column}>Title</SortableHeader>,
      cell: (ctx) => (
        <span className="text-[length:var(--text-src-triple)] font-medium text-primary">
          {String(ctx.getValue())}
        </span>
      ),
      sortUndefined: "last",
    },
    {
      accessorKey: "artist",
      size: 72,
      minSize: 48,
      maxSize: 560,
      header: ({ column }) => <SortableHeader column={column}>Artist</SortableHeader>,
      cell: (ctx) => (
        <span className="text-[length:var(--text-src-triple)] text-secondary">
          {String(ctx.getValue())}
        </span>
      ),
      sortUndefined: "last",
    },
    {
      accessorKey: "duration_ms",
      size: 56,
      minSize: 44,
      maxSize: 120,
      header: ({ column }) => (
        <SortableHeader column={column}>
          <span className="tabular-nums">Time</span>
        </SortableHeader>
      ),
      cell: (ctx) => (
        <span className="text-[length:var(--text-src-triple)] tabular-nums text-secondary">
          {formatDurationMs(ctx.getValue() as number | null)}
        </span>
      ),
      sortUndefined: "last",
      sortingFn: "basic",
    },
    {
      id: "top_match",
      accessorFn: (row) =>
        row.is_rejected_no_match
          ? "\0rejected"
          : row.top_match_below_minimum
            ? "\0belowmin"
            : row.top_match_score != null
              ? `${row.top_match_title ?? ""}\t${row.top_match_artist ?? ""}`
              : "",
      size: 88,
      minSize: 48,
      maxSize: 560,
      header: ({ column }) => (
        <SortableHeader column={column}>Best match</SortableHeader>
      ),
      cell: ({ row }) => <BestMatchCell row={row} />,
      sortUndefined: "last",
    },
    {
      id: "top_match_score",
      accessorFn: (row) => {
        if (row.is_rejected_no_match) return null;
        if (row.top_match_below_minimum) return null;
        return row.top_match_score ?? null;
      },
      size: 44,
      minSize: 36,
      maxSize: 96,
      header: ({ column }) => (
        <SortableHeader
          column={column}
          className="tabular-nums"
          title="Best match score"
        >
          Score
        </SortableHeader>
      ),
      cell: ({ row }) => <MatchScoreCell row={row} />,
      sortUndefined: "last",
      sortingFn: "basic",
    },
    {
      id: "playlists",
      accessorFn: (row) => (row.playlist_names ?? []).join(", "),
      size: 107,
      minSize: 56,
      maxSize: 480,
      header: ({ column }) => (
        <SortableHeader column={column}>Playlists</SortableHeader>
      ),
      cell: ({ row }) => {
        const names = row.original.playlist_names ?? [];
        if (!names.length) {
          return <span className="text-muted">—</span>;
        }
        return (
          <div className="flex flex-wrap items-center gap-0.5">
            {names.map((n, i) => (
              <span
                key={`${n}-${i}`}
                title={n}
                className={`inline-block max-w-full rounded-full border border-border bg-surface-2 px-1.5 py-px ${PLAYLIST_CHIP_TEXT} text-muted`}
              >
                {playlistChipLabel(n)}
              </span>
            ))}
          </div>
        );
      },
      sortUndefined: "last",
    },
    {
      id: "downloaded",
      accessorFn: (row) => (row.local_file_path ? 1 : 0),
      size: 44,
      minSize: 36,
      maxSize: 72,
      header: ({ column }) => (
        <SortableHeader column={column}>DL</SortableHeader>
      ),
      cell: ({ row }) => <DownloadedCell row={row} />,
      sortingFn: "basic",
    },
  ];
}
