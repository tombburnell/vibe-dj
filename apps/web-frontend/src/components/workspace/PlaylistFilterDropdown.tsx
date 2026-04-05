import { useEffect, useMemo, useRef, useState } from "react";

import type { Playlist } from "@/api/types";

type Props = {
  playlists: Playlist[];
  selectedIds: string[];
  onSelectedIdsChange: (ids: string[]) => void;
  isLoading: boolean;
  error: Error | null;
};

export function PlaylistFilterDropdown({
  playlists,
  selectedIds,
  onSelectedIdsChange,
  isLoading,
  error,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const sorted = useMemo(
    () => [...playlists].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" })),
    [playlists],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sorted;
    return sorted.filter((p) => p.name.toLowerCase().includes(q));
  }, [sorted, query]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const el = rootRef.current;
      if (el && !el.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const toggleId = (id: string) => {
    if (selectedSet.has(id)) {
      onSelectedIdsChange(selectedIds.filter((x) => x !== id));
    } else {
      onSelectedIdsChange([...selectedIds, id]);
    }
  };

  const activeCount = selectedIds.length;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={isLoading || Boolean(error)}
        title={error?.message}
        className={
          activeCount > 0
            ? "inline-flex items-center gap-1.5 rounded border border-accent bg-accent px-2 py-1 text-[0.75rem] font-medium text-white hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60 dark:text-background"
            : "inline-flex items-center gap-1.5 rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
        }
        onClick={() => setOpen((o) => !o)}
      >
        <span>Playlists</span>
        {isLoading ? (
          <span className="text-[0.65rem] opacity-80">…</span>
        ) : activeCount > 0 ? (
          <span className="min-w-[1.25rem] rounded-full bg-black/15 px-1 text-center tabular-nums dark:bg-black/25">
            {activeCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          className="absolute left-0 top-full z-50 mt-1 flex w-[min(100vw-1.5rem,18rem)] flex-col rounded-lg border border-border bg-surface-1 py-2 shadow-lg"
          role="dialog"
          aria-label="Filter by playlists"
        >
          <div className="border-b border-border px-3 pb-2">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search playlists…"
              aria-label="Search playlists"
              className="w-full rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-[0.75rem] text-primary placeholder:text-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
              autoFocus
            />
            {activeCount > 0 ? (
              <button
                type="button"
                className="mt-2 text-[0.7rem] font-medium text-accent hover:underline"
                onClick={() => onSelectedIdsChange([])}
              >
                Clear selection
              </button>
            ) : null}
          </div>

          <div className="max-h-60 overflow-y-auto px-1 pt-1" role="list">
            {error ? (
              <p className="px-2 py-2 text-[0.75rem] text-red-400">{error.message}</p>
            ) : filtered.length === 0 ? (
              <p className="px-2 py-3 text-[0.75rem] text-muted">
                {playlists.length === 0 ? "No playlists imported yet." : "No matching playlists."}
              </p>
            ) : (
              filtered.map((p) => {
                const checked = selectedSet.has(p.id);
                return (
                  <label
                    key={p.id}
                    role="listitem"
                    className="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-[0.75rem] hover:bg-surface-2"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleId(p.id)}
                      className="mt-0.5 shrink-0 rounded border-border"
                    />
                    <span className="min-w-0 break-words text-primary">{p.name}</span>
                  </label>
                );
              })
            )}
          </div>

          <p className="border-t border-border px-3 pt-2 text-[0.65rem] text-muted">
            No selection = all playlists. With selection, rows must belong to at least one chosen
            playlist.
          </p>
        </div>
      ) : null}
    </div>
  );
}
