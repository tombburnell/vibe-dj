import { useEffect, useMemo, useRef, useState } from "react";

import type { DlFilter } from "@/components/workspace/DlFilterSelect";
import {
  defaultSourceMatchCategoryFilter,
  SOURCE_MATCH_CATEGORY_KEYS,
  type SourceMatchCategoryFilterState,
} from "@/lib/sourceMatchCategory";

type Props = {
  dlFilter: DlFilter;
  onDlChange: (v: DlFilter) => void;
  matchCategoryFilter: SourceMatchCategoryFilterState;
  onMatchCategoryChange: (next: SourceMatchCategoryFilterState) => void;
};

const dlOptions: { value: DlFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "downloaded", label: "Downloaded" },
  { value: "not_downloaded", label: "Not downloaded" },
];

const categoryLabels: Record<keyof SourceMatchCategoryFilterState, string> = {
  picked: "Matched",
  ignored: "Ignored",
  rejected: "Missing",
  uncategorised: "Uncategorised",
};

function countCategoryOn(f: SourceMatchCategoryFilterState): number {
  return SOURCE_MATCH_CATEGORY_KEYS.filter((k) => f[k]).length;
}

function categoryFiltersEqual(
  a: SourceMatchCategoryFilterState,
  b: SourceMatchCategoryFilterState,
): boolean {
  return SOURCE_MATCH_CATEGORY_KEYS.every((k) => a[k] === b[k]);
}

function toggleCategory(
  f: SourceMatchCategoryFilterState,
  key: keyof SourceMatchCategoryFilterState,
): SourceMatchCategoryFilterState {
  return { ...f, [key]: !f[key] };
}

export function SourcesFiltersPopover({
  dlFilter,
  onDlChange,
  matchCategoryFilter,
  onMatchCategoryChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const activeCount = useMemo(() => {
    let n = 0;
    if (dlFilter !== "all") n += 1;
    const on = countCategoryOn(matchCategoryFilter);
    const neutral = on === 0 || on === SOURCE_MATCH_CATEGORY_KEYS.length;
    const sameAsDefault = categoryFiltersEqual(
      matchCategoryFilter,
      defaultSourceMatchCategoryFilter,
    );
    if (!neutral && !sameAsDefault) n += on;
    return n;
  }, [dlFilter, matchCategoryFilter]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const el = rootRef.current;
      if (el && !el.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        className={
          activeCount > 0
            ? "inline-flex items-center gap-1.5 rounded border border-accent bg-accent px-2 py-1 text-[0.75rem] font-medium text-white hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent dark:text-background"
            : "inline-flex items-center gap-1.5 rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        }
        onClick={() => setOpen((o) => !o)}
      >
        <span>Filters</span>
        {activeCount > 0 ? (
          <span className="min-w-[1.25rem] rounded-full bg-black/15 px-1 text-center tabular-nums dark:bg-black/25">
            {activeCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-[min(100vw-1.5rem,20rem)] rounded-lg border border-border bg-surface-1 p-3 shadow-lg"
          role="dialog"
          aria-label="Source filters"
        >
          <p className="mb-2 text-[0.7rem] text-muted">
            Downloaded and match category. Leave all category chips on or all off to show every
            category.
          </p>

          <div className="mb-3">
            <div className="mb-1.5 text-[0.65rem] font-medium uppercase tracking-wide text-muted">
              Downloaded
            </div>
            <div className="flex flex-wrap gap-1.5">
              {dlOptions.map((o) => {
                const selected = dlFilter === o.value;
                return (
                  <button
                    key={o.value}
                    type="button"
                    aria-pressed={selected}
                    className={
                      selected
                        ? "rounded-full border border-accent bg-accent px-2.5 py-1 text-[0.75rem] font-medium text-white dark:text-background"
                        : "rounded-full border border-border bg-surface-2 px-2.5 py-1 text-[0.75rem] text-primary hover:bg-surface-1"
                    }
                    onClick={() => onDlChange(o.value)}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="mb-1.5 text-[0.65rem] font-medium uppercase tracking-wide text-muted">
              Match category
            </div>
            <div className="flex flex-wrap gap-1.5">
              {SOURCE_MATCH_CATEGORY_KEYS.map((key) => {
                const selected = matchCategoryFilter[key];
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={selected}
                    className={
                      selected
                        ? "rounded-full border border-accent bg-accent px-2.5 py-1 text-[0.75rem] font-medium text-white dark:text-background"
                        : "rounded-full border border-border bg-surface-2 px-2.5 py-1 text-[0.75rem] text-primary hover:bg-surface-1"
                    }
                    onClick={() => onMatchCategoryChange(toggleCategory(matchCategoryFilter, key))}
                  >
                    {categoryLabels[key]}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
