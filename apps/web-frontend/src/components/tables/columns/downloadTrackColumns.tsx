import type { ColumnDef } from "@tanstack/react-table";

import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import { SortableHeader } from "../SortableHeader";

const PLAYLIST_CHIP_CHARS = 12;
const PLAYLIST_CHIP_TEXT =
  "text-[length:calc(var(--text-src-triple,0.8125rem)*0.66)] leading-tight";

function playlistChipLabel(name: string): string {
  const t = name.trim();
  if (t.length <= PLAYLIST_CHIP_CHARS) return t;
  return `${t.slice(0, PLAYLIST_CHIP_CHARS)}…`;
}

function BestLinkCell({ row }: { row: { original: SourceTrack } }) {
  const s = row.original;
  const url = s.amazon_url;
  const searched = s.amazon_last_searched_at != null;
  const label =
    (s.amazon_link_title?.trim() || (url ? "Amazon Music" : "")) || "";
  const tooltip = s.amazon_link_title?.trim() || url || "";
  const linkClass =
    "min-w-0 max-w-full truncate text-[length:var(--text-src-triple)] leading-none text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent";
  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        title={tooltip}
        className={`block ${linkClass}`}
      >
        {label}
      </a>
    );
  }
  if (searched) {
    return (
      <span className="text-[length:var(--text-src-triple)] leading-none text-muted">
        No link found
      </span>
    );
  }
  return (
    <span className="text-[length:var(--text-src-triple)] leading-none text-muted">
      —
    </span>
  );
}

export function buildDownloadTrackColumns(): ColumnDef<SourceTrack>[] {
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
      id: "best_link",
      accessorFn: (row) => row.amazon_url ?? "\0empty",
      size: 120,
      minSize: 64,
      maxSize: 400,
      header: ({ column }) => <SortableHeader column={column}>Link</SortableHeader>,
      cell: ({ row }) => <BestLinkCell row={row} />,
      sortUndefined: "last",
    },
    {
      id: "amazon_link_score",
      accessorFn: (row) => row.amazon_link_match_score ?? null,
      size: 44,
      minSize: 36,
      maxSize: 72,
      header: ({ column }) => (
        <SortableHeader column={column} className="tabular-nums">
          Score
        </SortableHeader>
      ),
      cell: ({ row }) => {
        const sc = row.original.amazon_link_match_score;
        return sc != null ? (
          <span className="text-[length:var(--text-src-triple)] tabular-nums text-secondary">
            {Math.round(sc)}%
          </span>
        ) : (
          <span className="text-[length:var(--text-src-triple)] text-muted">—</span>
        );
      },
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
      cell: ({ row }) => (row.original.local_file_path ? "✓" : "—"),
      sortingFn: "basic",
    },
  ];
}
