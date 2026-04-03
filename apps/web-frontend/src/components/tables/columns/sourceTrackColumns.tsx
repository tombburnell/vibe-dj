import type { ColumnDef } from "@tanstack/react-table";

import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import { SortableHeader } from "../SortableHeader";

export function buildSourceTrackColumns(): ColumnDef<SourceTrack>[] {
  return [
    {
      accessorKey: "title",
      size: 72,
      minSize: 48,
      maxSize: 560,
      header: ({ column }) => (
        <SortableHeader column={column}>Title</SortableHeader>
      ),
      cell: (ctx) => (
        <span className="font-medium text-primary">{String(ctx.getValue())}</span>
      ),
      sortUndefined: "last",
    },
    {
      accessorKey: "artist",
      size: 72,
      minSize: 48,
      maxSize: 560,
      header: ({ column }) => (
        <SortableHeader column={column}>Artist</SortableHeader>
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
        <span className="tabular-nums text-secondary">
          {formatDurationMs(ctx.getValue() as number | null)}
        </span>
      ),
      sortUndefined: "last",
      sortingFn: "basic",
    },
    {
      id: "playlists",
      accessorFn: (row) => row.playlist_names.join(", "),
      size: 160,
      minSize: 80,
      maxSize: 480,
      header: ({ column }) => (
        <SortableHeader column={column}>Playlists</SortableHeader>
      ),
      cell: ({ row }) => (
        <span className="text-muted">
          {row.original.playlist_names.length
            ? row.original.playlist_names.join(", ")
            : "—"}
        </span>
      ),
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
