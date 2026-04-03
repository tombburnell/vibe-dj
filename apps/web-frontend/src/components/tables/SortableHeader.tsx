import type { Column } from "@tanstack/react-table";
import clsx from "clsx";

type Props<TData, TValue> = {
  column: Column<TData, TValue>;
  children: React.ReactNode;
  className?: string;
};

/** Clickable header for TanStack Table client-side sort. */
export function SortableHeader<TData, TValue>({
  column,
  children,
  className,
}: Props<TData, TValue>) {
  if (!column.getCanSort()) {
    return <span className={className}>{children}</span>;
  }

  const sorted = column.getIsSorted();

  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center gap-0.5 rounded font-medium text-secondary",
        "hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
        className,
      )}
      onClick={column.getToggleSortingHandler()}
      aria-sort={
        sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
      }
    >
      {children}
      <span className="w-3 tabular-nums text-muted" aria-hidden>
        {sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : ""}
      </span>
    </button>
  );
}
