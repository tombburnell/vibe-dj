import type { Column } from "@tanstack/react-table";
import clsx from "clsx";

type Props<TData, TValue> = {
  column: Column<TData, TValue>;
  children: React.ReactNode;
  className?: string;
  title?: string;
};

/**
 * Column header for TanStack Table. Size and colour come from `index.css` tokens:
 * `--table-header-font-size`, `--table-header-text`, `--table-header-text-hover`,
 * `--table-header-sort-chevron` (see `@layer components` `.table-header-*`).
 */
export function SortableHeader<TData, TValue>({
  column,
  children,
  className,
  title,
}: Props<TData, TValue>) {
  if (!column.getCanSort()) {
    return (
      <span className={clsx("table-header-label", className)} title={title}>
        {children}
      </span>
    );
  }

  const sorted = column.getIsSorted();

  return (
    <button
      type="button"
      title={title}
      className={clsx(
        "table-header-sort-btn inline-flex items-center gap-0.5 rounded",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
        className,
      )}
      onClick={column.getToggleSortingHandler()}
      aria-sort={
        sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
      }
    >
      {children}
      <span
        className="table-header-sort-chevron w-3 tabular-nums"
        aria-hidden
      >
        {sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : ""}
      </span>
    </button>
  );
}
