import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import clsx from "clsx";
import { useState } from "react";

type Props<T> = {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  getRowId: (row: T) => string;
  selectedId: string | null;
  onRowClick: (row: T) => void;
  emptyMessage?: string;
};

export function DataTable<T>({
  data,
  columns,
  getRowId,
  selectedId,
  onRowClick,
  emptyMessage = "No rows",
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row, i) => getRowId(row) || String(i),
  });

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded border border-dashed border-border py-12 text-[var(--text-table)] text-muted"
        role="status"
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-auto rounded border border-border bg-surface-1">
      <table className="w-full border-collapse text-left text-[var(--text-table)]">
        <thead className="sticky top-0 z-10 bg-surface-2 shadow-sm">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-border">
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  className="whitespace-nowrap px-[var(--cell-px)] py-[var(--cell-py)]"
                  scope="col"
                  style={{ height: "var(--row-h)" }}
                >
                  {h.isPlaceholder
                    ? null
                    : flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const id = getRowId(row.original);
            const selected = id === selectedId;
            return (
              <tr
                key={row.id}
                className={clsx(
                  "cursor-pointer border-b border-[var(--color-row-divider)] transition-colors",
                  !selected && "hover:bg-[var(--color-row-hover)]",
                  selected && "bg-[var(--color-selection-bg)]",
                )}
                style={{
                  height: "var(--row-h)",
                  boxShadow: selected
                    ? "inset var(--selection-bar-width) 0 0 0 var(--color-selection-bar), inset calc(-1 * var(--selection-bar-width)) 0 0 0 var(--color-selection-bar)"
                    : undefined,
                }}
                onClick={() => onRowClick(row.original)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onRowClick(row.original);
                  }
                }}
                tabIndex={0}
                aria-selected={selected}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="whitespace-nowrap px-[var(--cell-px)] py-[var(--cell-py)] text-secondary"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
