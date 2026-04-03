type Props = { rows?: number; cols?: number };

export function TableSkeleton({ rows = 8, cols = 6 }: Props) {
  return (
    <div className="animate-pulse space-y-0 rounded border border-border bg-surface-1">
      <div
        className="flex border-b border-border bg-surface-2"
        style={{ height: "var(--row-h)" }}
      >
        {Array.from({ length: cols }).map((_, i) => (
          <div
            key={i}
            className="flex-1 border-r border-border/50 px-2 py-1 last:border-r-0"
          >
            <div className="h-3 w-2/3 rounded bg-border" />
          </div>
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="flex border-b border-border/60 last:border-b-0"
          style={{ height: "var(--row-h)" }}
        >
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="flex-1 border-r border-border/40 px-2 py-1 last:border-r-0"
            >
              <div className="h-2.5 w-4/5 rounded bg-border/70" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
