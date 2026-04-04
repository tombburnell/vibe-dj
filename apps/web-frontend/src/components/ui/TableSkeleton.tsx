import type { ReactNode } from "react";

type Props = { rows?: number; cols?: number; topChrome?: ReactNode };

/** Relative bar widths per column so skeleton roughly matches title/artist/time columns. */
function cellBarWidth(col: number): string {
  const patterns = [0.78, 0.62, 0.34, 0.58, 0.4, 0.36];
  return `${Math.round(patterns[col % patterns.length] * 100)}%`;
}

/**
 * Loading placeholder aligned with {@link DataTable}: outer + header use `border-border`;
 * body rows use `border-[var(--color-row-divider)]` only — no vertical column lines (those
 * were mistaken for “white” borders when `border-border/50` broke with CSS variables).
 */
export function TableSkeleton({ rows = 8, cols = 6, topChrome }: Props) {
  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-auto rounded border border-border bg-surface-1 animate-pulse"
      role="status"
      aria-label="Loading table"
    >
      {topChrome != null ? (
        <div
          className="shrink-0 bg-surface-2 px-[var(--cell-px)] py-1 text-[0.65rem] font-semibold uppercase tracking-wide text-muted shadow-sm"
          role="presentation"
        >
          {topChrome}
        </div>
      ) : null}
      <div
        className="flex shrink-0 border-b border-border bg-surface-2 shadow-sm"
        style={{ height: "var(--row-h)" }}
      >
        {Array.from({ length: cols }).map((_, i) => (
          <div
            key={i}
            className="flex min-w-0 flex-1 items-center px-[var(--cell-px)] py-[var(--cell-py)]"
          >
            <div
              className="h-3 max-w-[min(100%,10rem)] rounded-md bg-[var(--color-background)]"
              style={{ width: cellBarWidth(i) }}
            />
          </div>
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="flex border-b border-[var(--color-row-divider)] bg-surface-1"
          style={{ height: "var(--row-h)" }}
        >
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="flex min-w-0 flex-1 items-center px-[var(--cell-px)] py-[var(--cell-py)]"
            >
              <div
                className="h-2.5 max-w-[min(100%,14rem)] rounded-md bg-[var(--color-border)]"
                style={{ width: cellBarWidth(c + r) }}
              />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
