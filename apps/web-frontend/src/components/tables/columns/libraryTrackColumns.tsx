import type { ColumnDef } from "@tanstack/react-table";

import type { LibraryTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import { SortableHeader } from "../SortableHeader";

export function buildLibraryTrackColumns(): ColumnDef<LibraryTrack>[] {
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
      header: ({ column }) => (
        <SortableHeader column={column}>Artist</SortableHeader>
      ),
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
      accessorKey: "bpm",
      size: 52,
      minSize: 44,
      maxSize: 100,
      header: ({ column }) => (
        <SortableHeader column={column}>
          <span className="tabular-nums">BPM</span>
        </SortableHeader>
      ),
      cell: (ctx) => {
        const v = ctx.getValue() as number | null;
        return (
          <span className="text-[length:var(--text-src-triple)] tabular-nums">
            {v != null ? v.toFixed(1) : "—"}
          </span>
        );
      },
      sortUndefined: "last",
      sortingFn: "basic",
    },
    {
      accessorKey: "musical_key",
      size: 44,
      minSize: 36,
      maxSize: 80,
      header: ({ column }) => (
        <SortableHeader column={column}>Key</SortableHeader>
      ),
      cell: (ctx) => {
        const v = ctx.getValue() as string | null | undefined;
        return (
          <span className="text-[length:var(--text-src-triple)]">
            {v != null && v !== "" ? v : "—"}
          </span>
        );
      },
      sortUndefined: "last",
    },
    {
      accessorKey: "genre",
      size: 100,
      minSize: 56,
      maxSize: 400,
      header: ({ column }) => (
        <SortableHeader column={column}>Genre</SortableHeader>
      ),
      cell: (ctx) => {
        const v = ctx.getValue() as string | null | undefined;
        return (
          <span className="text-[length:var(--text-src-triple)]">
            {v != null && v !== "" ? v : "—"}
          </span>
        );
      },
      sortUndefined: "last",
    },
  ];
}
