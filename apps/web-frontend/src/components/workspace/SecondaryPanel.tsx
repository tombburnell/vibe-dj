import { useCallback, useState } from "react";

import type { LibraryTrack } from "@/api/types";
import type { MatchCandidate } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";

import type { MainView } from "./MainViewTabs";

/** One-line label for a purchase/search link (not the raw URL). */
function linkListLabel(
  title: string | null | undefined,
  artist: string | null | undefined,
  fallback: string,
): string {
  const parts = [title?.trim(), artist?.trim()].filter(Boolean);
  return parts.length > 0 ? parts.join(" — ") : fallback;
}

function CopyUrlIconButton({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard may be denied */
    }
  }, [url]);

  return (
    <button
      type="button"
      onClick={() => void onCopy()}
      title={copied ? "Copied!" : "Copy URL"}
      aria-label={copied ? "URL copied to clipboard" : "Copy URL to clipboard"}
      className="shrink-0 rounded border border-border/60 bg-surface-1 p-1 text-muted transition-colors hover:bg-surface-2 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
    >
      <svg
        className="size-3.5"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <rect x="9" y="9" width="13" height="13" rx="2" />
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
      </svg>
    </button>
  );
}

/** 0–1 title/artist fuzzy quality from API; lower → orange / red on the line. */
function candidateComponentClass(
  score: number,
  role: "title" | "artist",
): string {
  if (score >= 0.72) {
    return role === "title" ? "font-medium text-primary" : "text-secondary";
  }
  if (score >= 0.45) {
    return role === "title" ? "font-medium text-orange-500" : "text-orange-500";
  }
  return role === "title" ? "font-medium text-red-500" : "text-red-500";
}

type Props = {
  mainView: MainView;
  /** Single-row focus (exactly one source selected). */
  selectedSource: SourceTrack | null;
  selectedLibrary: LibraryTrack | null;
  /** Number of selected source rows (0 / 1 / many). */
  sourceSelectionCount: number;
  /** Merged rows for current multi-selection (length ≥ 2 when bulk UI). */
  selectedSourcesBulk: SourceTrack[];
  candidates: MatchCandidate[];
  candidatesLoading: boolean;
  candidatesError: Error | null;
  matchActionBusy: boolean;
  wishlistBusy: boolean;
  findLinksBusy: boolean;
  downloadQueueCount: number;
  onFindLinksDisplayed: () => void;
  onReSearchSelectedDownloads: () => void;
  onPickCandidate: (c: MatchCandidate) => void | Promise<void>;
  onPickTopMatch: () => void | Promise<void>;
  onRejectNoMatch: () => void | Promise<void>;
  onUndoPick: () => void | Promise<void>;
  onUndoReject: () => void | Promise<void>;
  onPickSelectedMatches: () => void | Promise<void>;
  onRejectSelectedMatches: () => void | Promise<void>;
  onWishlistSources: (ids: string[], onWishlist: boolean) => void | Promise<void>;
};

export function SecondaryPanel({
  mainView,
  selectedSource,
  selectedLibrary,
  sourceSelectionCount,
  selectedSourcesBulk,
  candidates,
  candidatesLoading,
  candidatesError,
  matchActionBusy,
  wishlistBusy,
  findLinksBusy,
  downloadQueueCount,
  onFindLinksDisplayed,
  onReSearchSelectedDownloads,
  onPickCandidate,
  onPickTopMatch,
  onRejectNoMatch,
  onUndoPick,
  onUndoReject,
  onPickSelectedMatches,
  onRejectSelectedMatches,
  onWishlistSources,
}: Props) {
  if (mainView === "download") {
    if (sourceSelectionCount === 0) {
      return (
        <PanelChrome title="Links">
          <p className="text-[var(--text-table)] text-muted">
            Select a Download row to see the best link and other URLs. Toolbar: Find links runs a
            throttled search for every track in the queue ({downloadQueueCount}).
          </p>
        </PanelChrome>
      );
    }

    if (sourceSelectionCount > 1) {
      const ignoreable = selectedSourcesBulk.filter((s) => s.on_wishlist);
      return (
        <PanelChrome title="Links">
          <p className="mb-2 text-[0.7rem] text-muted">
            {sourceSelectionCount} tracks selected
          </p>
          <p className="mb-3 text-[0.7rem] text-[var(--text-table)] text-secondary">
            Re-search selected forces a new web search for each selected row (respects delay between
            requests).
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              disabled={findLinksBusy}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() => onFindLinksDisplayed()}
            >
              Find links (full queue)
            </button>
            <button
              type="button"
              disabled={findLinksBusy}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() => onReSearchSelectedDownloads()}
            >
              Re-search selected
            </button>
            <button
              type="button"
              disabled={wishlistBusy || ignoreable.length === 0}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() =>
                onWishlistSources(
                  ignoreable.map((s) => s.id),
                  false,
                )
              }
            >
              Ignore selected
              {ignoreable.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted">
                  ({ignoreable.length} on list)
                </span>
              ) : null}
            </button>
          </div>
        </PanelChrome>
      );
    }

    if (!selectedSource) {
      return (
        <PanelChrome title="Links">
          <p className="text-[var(--text-table)] text-muted">Loading selection…</p>
        </PanelChrome>
      );
    }

    const s = selectedSource;
    const candidates = s.amazon_candidates ?? [];
    const searched = s.amazon_last_searched_at != null;

    return (
      <PanelChrome title="Links">
        <p className="mb-2 text-[0.7rem] text-muted">
          {s.artist} — {s.title}
        </p>
        <div className="mb-3 space-y-2 rounded border border-border/70 bg-surface-2/50 px-2 py-2 text-[0.7rem] text-[var(--text-table)]">
          <div className="font-medium text-secondary">Best link</div>
          {s.amazon_url ? (
            <div className="space-y-1">
              <div className="grid grid-cols-[minmax(0,1fr)_2.75rem_auto] items-center gap-x-2 text-[0.55rem] font-medium uppercase tracking-wide text-muted">
                <span>Title</span>
                <span className="text-right">Score</span>
                <span className="sr-only">Copy</span>
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)_2.75rem_auto] items-center gap-x-2">
                <a
                  href={s.amazon_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-w-0 font-medium leading-snug text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
                  title={s.amazon_link_title?.trim() || s.amazon_url}
                >
                  {s.amazon_link_title?.trim() ||
                    linkListLabel(null, null, "Amazon Music")}
                </a>
                <span className="shrink-0 text-right tabular-nums text-[0.65rem] text-secondary">
                  {s.amazon_link_match_score != null
                    ? `${Math.round(s.amazon_link_match_score)}%`
                    : "—"}
                </span>
                <CopyUrlIconButton url={s.amazon_url} />
              </div>
            </div>
          ) : searched ? (
            <p className="text-muted">No direct link found (search already run).</p>
          ) : (
            <p className="text-muted">Not searched yet — use Find links.</p>
          )}
          {s.amazon_price ? (
            <p className="tabular-nums text-muted">Price: {s.amazon_price}</p>
          ) : null}
          {s.amazon_search_url ? (
            <div className="flex items-start gap-2 text-[0.65rem]">
              <a
                href={s.amazon_search_url}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-0 flex-1 font-medium leading-snug text-accent underline decoration-accent/40 underline-offset-2"
              >
                Amazon search
              </a>
              <CopyUrlIconButton url={s.amazon_search_url} />
            </div>
          ) : null}
        </div>
        <div className="text-[0.65rem] font-medium uppercase tracking-wide text-secondary">
          Other links
        </div>
        {candidates.length === 0 ? (
          <p className="mt-1 text-[var(--text-table)] text-muted">
            {searched ? "No alternate URLs." : "Run Find links to populate."}
          </p>
        ) : (
          <ul className="mt-1 space-y-2">
            {candidates.map((c, i) => (
              <li
                key={`${c.url}-${i}`}
                className="rounded-md border-0 bg-neutral-300/80 px-2 py-1.5 text-[0.6rem] leading-snug dark:bg-neutral-800/85"
              >
                <div className="grid grid-cols-[minmax(0,1fr)_2.75rem_auto] items-center gap-x-2">
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="min-w-0 font-medium leading-snug text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
                    title={c.url}
                  >
                    {linkListLabel(c.title, c.artist, "Amazon link")}
                  </a>
                  <span className="shrink-0 text-right tabular-nums text-muted">
                    {c.match_score != null ? `${Math.round(c.match_score)}%` : "—"}
                  </span>
                  <CopyUrlIconButton url={c.url} />
                </div>
                {c.price ? (
                  <div className="mt-1 tabular-nums text-muted">{c.price}</div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/60 pt-2">
          {s.on_wishlist ? (
            <button
              type="button"
              disabled={wishlistBusy}
              className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
              title="Hide from Sources / Download — not deleting the track"
              onClick={() => onWishlistSources([s.id], false)}
            >
              Ignore
            </button>
          ) : (
            <button
              type="button"
              disabled={wishlistBusy}
              className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
              onClick={() => onWishlistSources([s.id], true)}
            >
              Restore to list
            </button>
          )}
        </div>
      </PanelChrome>
    );
  }

  if (mainView === "sources") {
    if (sourceSelectionCount === 0) {
      return (
        <PanelChrome title="Matches">
          <p className="text-[var(--text-table)] text-muted">
            Select source row(s). Use Ctrl/Cmd+click to add rows; Shift+click for a range. One row:
            current match and candidates. Several rows: bulk actions.
          </p>
        </PanelChrome>
      );
    }

    if (sourceSelectionCount > 1) {
      const pickable = selectedSourcesBulk.filter(
        (s) =>
          s.top_match_library_track_id != null &&
          s.top_match_score != null &&
          !s.is_rejected_no_match &&
          !s.top_match_is_picked &&
          !s.top_match_below_minimum,
      );
      const ignoreableBulk = selectedSourcesBulk.filter((s) => s.on_wishlist);
      const restorableBulk = selectedSourcesBulk.filter((s) => !s.on_wishlist);
      return (
        <PanelChrome title="Matches">
          <p className="mb-2 text-[0.7rem] text-muted">
            {sourceSelectionCount} tracks selected
          </p>
          <p className="mb-3 text-[0.7rem] text-[var(--text-table)] text-secondary">
            Match applies each row&apos;s current best library row (from the table). Rows without a
            candidate, marked Need, or already matched are skipped.
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              disabled={matchActionBusy || pickable.length === 0}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() => void onPickSelectedMatches()}
            >
              Match selected
              {pickable.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted">({pickable.length} eligible)</span>
              ) : null}
            </button>
            <button
              type="button"
              disabled={matchActionBusy}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() => void onRejectSelectedMatches()}
            >
              Mark selected as Need
            </button>
            <button
              type="button"
              disabled={wishlistBusy || ignoreableBulk.length === 0}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() =>
                onWishlistSources(
                  ignoreableBulk.map((s) => s.id),
                  false,
                )
              }
            >
              Ignore selected
              {ignoreableBulk.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted">
                  ({ignoreableBulk.length} on list)
                </span>
              ) : null}
            </button>
            <button
              type="button"
              disabled={wishlistBusy || restorableBulk.length === 0}
              className="rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left text-[0.75rem] text-primary hover:bg-surface-1 disabled:opacity-50"
              onClick={() =>
                onWishlistSources(
                  restorableBulk.map((s) => s.id),
                  true,
                )
              }
            >
              Restore selected to list
              {restorableBulk.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted">
                  ({restorableBulk.length} ignored)
                </span>
              ) : null}
            </button>
          </div>
        </PanelChrome>
      );
    }

    if (!selectedSource) {
      return (
        <PanelChrome title="Matches">
          <p className="text-[var(--text-table)] text-muted">Loading selection…</p>
        </PanelChrome>
      );
    }

    const rejected = selectedSource.is_rejected_no_match === true;
    const picked = selectedSource.top_match_is_picked === true;
    const belowMin = selectedSource.top_match_below_minimum === true;
    const hasTop =
      (selectedSource.top_match_title != null || selectedSource.top_match_score != null) &&
      !belowMin;
    const topId = selectedSource.top_match_library_track_id ?? null;
    const topScore = selectedSource.top_match_score;
    const canPickTop =
      hasTop &&
      !picked &&
      !rejected &&
      !belowMin &&
      topId != null &&
      topScore != null;
    const topSectionHeading = rejected
      ? "Need"
      : belowMin
        ? "Best match"
        : !hasTop
          ? "Best match"
          : picked
            ? "Matched"
            : "Top candidate";
    const candidatesVisible =
      topId == null ? candidates : candidates.filter((c) => c.id !== topId);

    return (
      <PanelChrome title="Matches">
        <p className="mb-2 text-[0.7rem] text-muted">
          {selectedSource.artist} — {selectedSource.title}
        </p>

        <div className="mb-3 space-y-2 rounded border border-border/70 bg-surface-2/50 px-2 py-2 text-[0.7rem] text-[var(--text-table)]">
          <div className="font-medium text-secondary">{topSectionHeading}</div>
          {rejected ? (
            <p className="text-muted">Need — not in library for this snapshot scope.</p>
          ) : belowMin ? (
            <p className="text-[0.55rem] leading-tight text-muted">
              Minimum score not met
            </p>
          ) : hasTop ? (
            <div>
              <div className="text-primary">
                {picked ? (
                  <span className="mr-1 text-emerald-500" title="Manually matched">
                    ✓
                  </span>
                ) : null}
                {selectedSource.top_match_title ?? "—"}
              </div>
              <div className="text-secondary">{selectedSource.top_match_artist ?? "—"}</div>
              {selectedSource.top_match_score != null ? (
                <div className="tabular-nums text-muted">
                  {Math.round(selectedSource.top_match_score * 100)}% ·{" "}
                  {formatDurationMs(selectedSource.top_match_duration_ms)}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-muted">No match yet (below min score or no library).</p>
          )}

          <div className="flex flex-wrap gap-1.5 pt-1">
            {!rejected ? (
              <>
                {canPickTop ? (
                  <button
                    type="button"
                    disabled={matchActionBusy}
                    className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                    onClick={() => void onPickTopMatch()}
                  >
                    Match
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={matchActionBusy}
                  className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                  onClick={() => void onRejectNoMatch()}
                >
                  Need (no match)
                </button>
              </>
            ) : (
              <button
                type="button"
                disabled={matchActionBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => void onUndoReject()}
              >
                Undo Need
              </button>
            )}
            {picked ? (
              <button
                type="button"
                disabled={matchActionBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => void onUndoPick()}
              >
                Undo match
              </button>
            ) : null}
            {selectedSource.on_wishlist ? (
              <button
                type="button"
                disabled={matchActionBusy || wishlistBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                title="Hide from Sources / Download — not deleting the track"
                onClick={() => onWishlistSources([selectedSource.id], false)}
              >
                Ignore
              </button>
            ) : (
              <button
                type="button"
                disabled={wishlistBusy}
                className="rounded border border-border/80 bg-surface-1 px-2 py-0.5 text-[0.65rem] text-primary hover:bg-surface-2 disabled:opacity-50"
                onClick={() => onWishlistSources([selectedSource.id], true)}
              >
                Restore to list
              </button>
            )}
          </div>
        </div>

        <div className="text-[0.65rem] font-medium uppercase tracking-wide text-secondary">
          Candidates
        </div>
        {candidatesError ? (
          <p className="mt-1 text-[var(--text-table)] text-red-400">{candidatesError.message}</p>
        ) : candidatesLoading ? (
          <p className="mt-1 text-[var(--text-table)] text-muted">Loading candidates…</p>
        ) : candidatesVisible.length === 0 ? (
          <p className="mt-1 text-[var(--text-table)] text-muted">No candidates for this source.</p>
        ) : (
          <ul className="mt-1 space-y-2">
            {candidatesVisible.map((c) => {
              const isCurrent = topId != null && c.id === topId;
              const titleS = c.title_match_score;
              const artistS = c.artist_match_score;
              return (
                <li
                  key={c.id}
                  className={`rounded-md border-0 px-2 py-1.5 text-[0.6rem] leading-snug ${
                    isCurrent
                      ? "bg-emerald-950/25 ring-1 ring-emerald-600/35 dark:bg-emerald-950/20"
                      : "bg-neutral-300/80 dark:bg-neutral-800/85"
                  }`}
                >
                  <div className="flex gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex min-w-0 flex-wrap items-baseline gap-x-1 gap-y-0">
                        <span
                          className={`min-w-0 flex-1 truncate ${candidateComponentClass(titleS, "title")}`}
                        >
                          {c.title}
                        </span>
                        <span className="shrink-0 italic tabular-nums text-muted">
                          {Math.round(titleS * 100)}%
                        </span>
                      </div>
                      <div className="mt-px flex min-w-0 flex-wrap items-baseline gap-x-1 gap-y-0">
                        <span
                          className={`min-w-0 flex-1 truncate ${candidateComponentClass(artistS, "artist")}`}
                        >
                          {c.artist}
                        </span>
                        <span className="shrink-0 italic tabular-nums text-muted">
                          {Math.round(artistS * 100)}%
                        </span>
                      </div>
                      <div className="mt-1 tabular-nums text-[0.52rem] text-muted">
                        {formatDurationMs(c.duration_ms)} ·{" "}
                        {c.bpm != null ? `${c.bpm} BPM` : "—"} · {c.musical_key ?? "—"}
                      </div>
                      <button
                        type="button"
                        disabled={matchActionBusy || rejected}
                        className="mt-1 rounded border border-border/50 bg-surface-1 px-1.5 py-0.5 text-[0.58rem] text-primary hover:bg-surface-2 disabled:opacity-50 dark:bg-surface-2/80"
                        onClick={() => void onPickCandidate(c)}
                      >
                        Match
                      </button>
                    </div>
                    <div className="shrink-0 self-start tabular-nums text-[0.68rem] font-semibold text-primary">
                      {Math.round(c.match_score * 100)}%
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </PanelChrome>
    );
  }

  if (!selectedLibrary) {
    return (
      <PanelChrome title="Details">
        <p className="text-[var(--text-table)] text-muted">
          Select a library row for path and metadata.
        </p>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Library file">
      <dl className="space-y-2 text-[var(--text-table)]">
        <div>
          <dt className="text-muted">Path</dt>
          <dd className="break-all font-mono text-[0.7rem] text-secondary">
            {selectedLibrary.file_path}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Track</dt>
          <dd className="text-primary">
            {selectedLibrary.artist} — {selectedLibrary.title}
          </dd>
        </div>
      </dl>
    </PanelChrome>
  );
}

function PanelChrome({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      className="flex h-full min-h-0 flex-col rounded border border-border bg-surface-1"
      aria-label={title}
    >
      <header className="border-b border-border bg-surface-2 px-2 py-1.5 text-[0.7rem] font-semibold uppercase tracking-wide text-secondary">
        {title}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-2">{children}</div>
    </section>
  );
}
