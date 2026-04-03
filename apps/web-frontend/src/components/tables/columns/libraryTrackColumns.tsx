import type { ColumnDef } from "@tanstack/react-table";

import type { LibraryTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import { SortableHeader } from "../SortableHeader";

export function buildLibraryTrackColumns(): ColumnDef<LibraryTrack>[] {
  return [
    {
      accessorKey: "title",
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
      header: ({ column }) => (
        <SortableHeader column={column}>Artist</SortableHeader>
      ),
      sortUndefined: "last",
    },
    {
      accessorKey: "duration_ms",
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
      accessorKey: "bpm",
      header: ({ column }) => (
        <SortableHeader column={column}>
          <span className="tabular-nums">BPM</span>
        </SortableHeader>
      ),
      cell: (ctx) => {
        const v = ctx.getValue() as number | null;
        return <span className="tabular-nums">{v != null ? v.toFixed(1) : "—"}</span>;
      },
      sortUndefined: "last",
      sortingFn: "basic",
    },
    {
      accessorKey: "musical_key",
      header: ({ column }) => (
        <SortableHeader column={column}>Key</SortableHeader>
      ),
      sortUndefined: "last",
    },
    {
      accessorKey: "genre",
      header: ({ column }) => (
        <SortableHeader column={column}>Genre</SortableHeader>
      ),
      sortUndefined: "last",
    },
  ];
}
