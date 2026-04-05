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
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
  type Ref,
} from "react";
import type {
  Dispatch,
  MouseEvent as ReactMouseEvent,
  SetStateAction,
} from "react";

/** Internal column: absorbs remaining panel width so data columns keep fixed px sizes while resizing. */
const TABLE_FILL_COLUMN_ID = "__tmTableFill";

/**
 * Listen on `window` (capture) so drag keeps working while React re-renders every move
 * (`setColumnWidths` updates thead/tbody). Listeners on the resize handle’s element are lost when
 * that DOM node is replaced; `setPointerCapture` does not survive a new node for the same fiber slot.
 */
function bindColumnResizeWindowPointerDrag(
  win: Window,
  pointerId: number,
  setColumnWidths: Dispatch<SetStateAction<Record<string, number>>>,
  setResizingColumnId: (id: string | null) => void,
  columnId: string,
  min: number,
  max: number,
  startClientX: number,
  startSize: number,
) {
  const applyClientX = (clientX: number) => {
    const delta = clientX - startClientX;
    const next = Math.round(Math.min(max, Math.max(min, startSize + delta)));
    setColumnWidths((old) =>
      old[columnId] === next ? old : { ...old, [columnId]: next },
    );
  };

  const moveOpts: AddEventListenerOptions = { capture: true, passive: false };
  const endOpts: AddEventListenerOptions = { capture: true };

  const onMove = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    e.preventDefault();
    applyClientX(e.clientX);
  };

  const onEnd = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    applyClientX(e.clientX);
    win.removeEventListener("pointermove", onMove, moveOpts);
    win.removeEventListener("pointerup", onEnd, endOpts);
    win.removeEventListener("pointercancel", onEnd, endOpts);
    setResizingColumnId(null);
  };

  win.addEventListener("pointermove", onMove, moveOpts);
  win.addEventListener("pointerup", onEnd, endOpts);
  win.addEventListener("pointercancel", onEnd, endOpts);
}

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
  /** Full-width strip above column headers (inside the table panel border). */
  topChrome?: ReactNode;
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
  topChrome,
}: Props<T>) {
  /** Multi-select tables: avoid drag-selecting text across rows; cells stay `select-text`. */
  const multiSelectCellText = selectedIds !== undefined;

  const [sorting, setSorting] = useState<SortingState>([]);
  const [resizingColumnId, setResizingColumnId] = useState<string | null>(null);
  /** Pixel widths keyed by column id — avoids TanStack columnSizing + controlled `sorting` merge edge cases. */
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [containerWidth, setContainerWidth] = useState(0);
  const innerScrollRef = useRef<HTMLDivElement | null>(null);

  const columnsWithFill = useMemo((): ColumnDef<T, unknown>[] => {
    const fill: ColumnDef<T, unknown> = {
      id: TABLE_FILL_COLUMN_ID,
      accessorFn: () => null,
      header: () => null,
      cell: () => null,
      size: 0,
      minSize: 0,
      maxSize: 99_999,
      enableResizing: false,
      enableSorting: false,
    };
    return [...columns, fill];
  }, [columns]);

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
    columns: columnsWithFill,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row, i) => getRowId(row) || String(i),
    enableSorting,
    enableColumnResizing: false,
    defaultColumn: {
      minSize: 40,
      maxSize: 640,
      size: 120,
    },
  });

  useLayoutEffect(() => {
    if (data.length === 0) {
      setContainerWidth(0);
      return;
    }
    const el = innerScrollRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setContainerWidth(el.clientWidth));
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, [data.length]);

  const dataColumnsTotal = table
    .getVisibleLeafColumns()
    .filter((c) => c.id !== TABLE_FILL_COLUMN_ID)
    .reduce((sum, c) => {
      const min = c.columnDef.minSize ?? 40;
      const max = c.columnDef.maxSize ?? 640;
      const raw = columnWidths[c.id] ?? c.getSize();
      return sum + Math.min(max, Math.max(min, raw));
    }, 0);
  const tableWidth = Math.max(containerWidth, dataColumnsTotal);
  const fillWidth = Math.max(0, tableWidth - dataColumnsTotal);

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

  const leafColumns = table.getVisibleLeafColumns();
  const leafColCount = leafColumns.length;
  const leafColWidths = leafColumns.map((c) => {
    if (c.id === TABLE_FILL_COLUMN_ID) return fillWidth;
    const min = c.columnDef.minSize ?? 40;
    const max = c.columnDef.maxSize ?? 640;
    const raw = columnWidths[c.id] ?? c.getSize();
    return Math.min(max, Math.max(min, raw));
  });

  if (data.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded border border-border bg-surface-1">
        {topChrome != null ? (
          <div
            className="shrink-0 bg-surface-2 px-[var(--cell-px)] py-1 text-[0.65rem] font-semibold uppercase tracking-wide text-muted shadow-sm"
            role="presentation"
          >
            {topChrome}
          </div>
        ) : null}
        <div
          className="flex flex-1 items-center justify-center px-[var(--cell-px)] py-12 text-center text-[var(--text-table)] text-muted"
          role="status"
        >
          {emptyMessage}
        </div>
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
          width: tableWidth,
          tableLayout: "fixed",
        }}
      >
        {/*
          Column widths must live on <col> — the first row is often topChrome with one cell spanning
          all columns; in fixed layout that row otherwise defines the grid and ignores per-th/td widths.
        */}
        <colgroup>
          {leafColumns.map((c, i) => (
            <col key={c.id} style={{ width: leafColWidths[i] }} />
          ))}
        </colgroup>
        <thead className="sticky top-0 z-10 bg-surface-2 shadow-sm">
          {topChrome != null ? (
            <tr>
              <th
                className="px-[var(--cell-px)] py-1 text-left text-[0.65rem] font-semibold uppercase tracking-wide text-muted"
                colSpan={leafColCount}
                scope="colgroup"
              >
                {topChrome}
              </th>
            </tr>
          ) : null}
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-border">
              {hg.headers.map((h) => {
                const isFill = h.column.id === TABLE_FILL_COLUMN_ID;
                const col = h.column;
                const minW = col.columnDef.minSize ?? 40;
                const maxW = col.columnDef.maxSize ?? 640;
                const showResize =
                  !isFill &&
                  !h.isPlaceholder &&
                  h.colSpan === 1 &&
                  (col.columnDef.enableResizing ?? true);
                return (
                  <th
                    key={h.id}
                    className={clsx(
                      "relative whitespace-nowrap py-[var(--cell-py)]",
                      !isFill && "px-[var(--cell-px)]",
                      isFill && "p-0",
                    )}
                    scope="col"
                    aria-hidden={isFill ? true : undefined}
                    style={{
                      height: "var(--row-h)",
                    }}
                  >
                    {h.isPlaceholder ? null : (
                      <>
                        {!isFill ? (
                          <div className="overflow-hidden text-ellipsis pr-1">
                            {flexRender(
                              h.column.columnDef.header,
                              h.getContext(),
                            )}
                          </div>
                        ) : null}
                        {showResize ? (
                          <div
                            role="separator"
                            aria-orientation="vertical"
                            aria-label={`Resize ${String(col.id)} column`}
                            style={{ touchAction: "none" }}
                            onPointerDown={(e) => {
                              if (e.button !== 0) return;
                              e.preventDefault();
                              e.stopPropagation();
                              setResizingColumnId(col.id);
                              const startSize = Math.min(
                                maxW,
                                Math.max(
                                  minW,
                                  columnWidths[col.id] ?? col.getSize(),
                                ),
                              );
                              const win =
                                (e.currentTarget as HTMLElement).ownerDocument
                                  .defaultView ?? window;
                              bindColumnResizeWindowPointerDrag(
                                win,
                                e.pointerId,
                                setColumnWidths,
                                setResizingColumnId,
                                col.id,
                                minW,
                                maxW,
                                e.clientX,
                                startSize,
                              );
                            }}
                            className={clsx(
                              "absolute right-0 top-0 z-30 h-full min-w-[12px] touch-none select-none",
                              "cursor-col-resize border-r border-transparent hover:border-accent/80",
                              resizingColumnId === col.id &&
                                "border-accent bg-accent/20",
                            )}
                          />
                        ) : null}
                      </>
                    )}
                  </th>
                );
              })}
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
                {row.getVisibleCells().map((cell) => {
                  const isFill = cell.column.id === TABLE_FILL_COLUMN_ID;
                  return (
                  <td
                    key={cell.id}
                    className={clsx(
                      "overflow-hidden py-0 text-secondary",
                      !isFill && "px-[var(--cell-px)]",
                      isFill && "p-0",
                      multiSelectCellText && "select-text",
                    )}
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
                  );
                })}
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
