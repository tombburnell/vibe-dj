import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import clsx from "clsx";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MutableRefObject,
  type Ref,
} from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

type Props<T> = {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  getRowId: (row: T) => string;
  /** Single-selection highlight (library table). Ignored when `selectedIds` is set. */
  selectedId?: string | null;
  /**
   * Multi-selection highlight (source / download tables). When set, rows use `user-select: none`
   * and cells `user-select: text` so range selection does not drag-highlight text across rows.
   */
  selectedIds?: string[];
  onRowClick: (row: T, event?: ReactMouseEvent<HTMLTableRowElement>) => void;
  emptyMessage?: string;
  /** When false, headers are not sortable (e.g. server-paginated library). */
  enableSorting?: boolean;
  /** Outer scroll container (for visibility / virtual helpers). */
  scrollContainerRef?: Ref<HTMLDivElement>;
  /** Fire when the scroll container is near the bottom (infinite scroll). */
  onNearEnd?: () => void;
  hasMore?: boolean;
  isLoadingMore?: boolean;
  /** Current visual row order (after sort) — for Shift+click range selection on source table. */
  onDisplayRowOrder?: (rowIdsInOrder: string[]) => void;
};

export function DataTable<T>({
  data,
  columns,
  getRowId,
  selectedId = null,
  selectedIds,
  onRowClick,
  emptyMessage = "No rows",
  enableSorting = true,
  scrollContainerRef,
  onNearEnd,
  hasMore = false,
  isLoadingMore = false,
  onDisplayRowOrder,
}: Props<T>) {
  /** Multi-select tables: avoid drag-selecting text across rows; cells stay `select-text`. */
  const multiSelectCellText = selectedIds !== undefined;

  const [sorting, setSorting] = useState<SortingState>([]);
  const innerScrollRef = useRef<HTMLDivElement | null>(null);

  const assignScrollRef = useCallback(
    (node: HTMLDivElement | null) => {
      innerScrollRef.current = node;
      const r = scrollContainerRef;
      if (!r) return;
      if (typeof r === "function") r(node);
      else (r as MutableRefObject<HTMLDivElement | null>).current = node;
    },
    [scrollContainerRef],
  );

  /** Shift/Cmd/Ctrl row selection must not extend a browser text selection across cells. */
  const onRowMouseDownMulti = useCallback(
    (e: ReactMouseEvent<HTMLTableRowElement>) => {
      if (!multiSelectCellText) return;
      if (e.shiftKey || e.metaKey || e.ctrlKey) {
        e.preventDefault();
        document.getSelection()?.removeAllRanges();
      }
    },
    [multiSelectCellText],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row, i) => getRowId(row) || String(i),
    enableSorting,
    columnResizeMode: "onChange",
    enableColumnResizing: true,
    defaultColumn: {
      minSize: 40,
      maxSize: 640,
      size: 120,
    },
  });

  useEffect(() => {
    if (!onDisplayRowOrder) return;
    onDisplayRowOrder(
      table.getRowModel().rows.map((row) => getRowId(row.original)),
    );
  }, [data, sorting, getRowId, onDisplayRowOrder, table]);

  useEffect(() => {
    const el = innerScrollRef.current;
    if (!el || !onNearEnd) return;

    const onScroll = () => {
      if (!hasMore || isLoadingMore) return;
      const threshold = 320;
      if (el.scrollHeight - el.scrollTop - el.clientHeight < threshold) {
        onNearEnd();
      }
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [onNearEnd, hasMore, isLoadingMore, data.length]);

  useEffect(() => {
    const el = innerScrollRef.current;
    if (!el || !onNearEnd || !hasMore || isLoadingMore) return;
    if (el.scrollHeight <= el.clientHeight + 8) {
      onNearEnd();
    }
  }, [data.length, hasMore, isLoadingMore, onNearEnd]);

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
    <div
      ref={assignScrollRef}
      className="flex min-h-0 flex-1 flex-col overflow-auto rounded border border-border bg-surface-1"
    >
      <table
        className="border-collapse text-left text-[var(--text-table)]"
        style={{
          width: table.getCenterTotalSize(),
          minWidth: "100%",
          tableLayout: "fixed",
        }}
      >
        <thead className="sticky top-0 z-10 bg-surface-2 shadow-sm">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-border">
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  className="relative whitespace-nowrap px-[var(--cell-px)] py-[var(--cell-py)]"
                  scope="col"
                  style={{
                    height: "var(--row-h)",
                    width: h.getSize(),
                    minWidth: h.getSize(),
                    maxWidth: h.getSize(),
                  }}
                >
                  {h.isPlaceholder ? null : (
                    <>
                      <div className="overflow-hidden text-ellipsis pr-1">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                      </div>
                      {h.column.getCanResize() ? (
                        <div
                          role="separator"
                          aria-orientation="vertical"
                          aria-label={`Resize ${String(h.column.id)} column`}
                          onMouseDown={h.getResizeHandler()}
                          onTouchStart={h.getResizeHandler()}
                          className={clsx(
                            "absolute right-0 top-0 z-20 h-full w-1.5 touch-none select-none",
                            "cursor-col-resize border-r border-transparent hover:border-accent/80",
                            h.column.getIsResizing() && "border-accent bg-accent/20",
                          )}
                        />
                      ) : null}
                    </>
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const id = getRowId(row.original);
            const selected = selectedIds
              ? selectedIds.includes(id)
              : id === selectedId;
            return (
              <tr
                key={row.id}
                data-row-id={id}
                className={clsx(
                  "cursor-pointer border-b border-[var(--color-row-divider)] transition-colors",
                  multiSelectCellText && "select-none",
                  !selected && "hover:bg-[var(--color-row-hover)]",
                  selected && "bg-[var(--color-selection-bg)]",
                )}
                style={{
                  height: "var(--row-h)",
                  boxShadow: selected
                    ? "inset var(--selection-bar-width) 0 0 0 var(--color-selection-bar), inset calc(-1 * var(--selection-bar-width)) 0 0 0 var(--color-selection-bar)"
                    : undefined,
                }}
                onMouseDown={onRowMouseDownMulti}
                onClick={(e) => {
                  onRowClick(row.original, e);
                  if (
                    multiSelectCellText &&
                    (e.shiftKey || e.metaKey || e.ctrlKey)
                  ) {
                    requestAnimationFrame(() =>
                      document.getSelection()?.removeAllRanges(),
                    );
                  }
                }}
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
                    className={clsx(
                      "overflow-hidden px-[var(--cell-px)] py-0 text-secondary",
                      multiSelectCellText && "select-text",
                    )}
                    style={{
                      width: cell.column.getSize(),
                      maxWidth: cell.column.getSize(),
                    }}
                  >
                    {/*
                      Row height is fixed (--row-h); padding lives inside this flex box so every
                      cell (plain text, links, inline-flex) shares the same vertical centering.
                    */}
                    <div className="box-border flex min-h-[var(--row-h)] min-w-0 items-center overflow-hidden text-ellipsis whitespace-nowrap py-[var(--cell-py)]">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </div>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {isLoadingMore ? (
        <div
          className="border-t border-border bg-surface-2 px-[var(--cell-px)] py-2 text-center text-[0.75rem] text-muted"
          role="status"
        >
          Loading more…
        </div>
      ) : null}
    </div>
  );
}
