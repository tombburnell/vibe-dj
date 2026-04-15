import { useCallback, useState } from "react";
import { HiArrowDownTray, HiArrowPath, HiNoSymbol, HiShoppingCart } from "react-icons/hi2";
import { SiBrave, SiGoogle } from "react-icons/si";

import type { LibraryTrack } from "@/api/types";
import type { MatchCandidate } from "@/api/types";
import type { SourceTrack } from "@/api/types";
import type { LinkSearchSpinTarget, WebSearchProvider } from "@/api/types";
import { formatDurationMs } from "@/lib/formatDuration";
import {
  collectNonBrokenAmazonLinkUrls,
  sortAmazonCandidatesForDisplay,
} from "@/lib/amazonLinkUtils";
import { bandcampBuyPageUrl, isBandcampUrl } from "@/lib/bandcampUrl";
import { isYoutubeUrl } from "@/lib/youtubeUrl";

import { LinkSiteIcon } from "@/components/LinkSiteIcon";

import type { MainView } from "./MainViewTabs";

/** Same token as DataTable body cells / source–download columns. */
const PANEL_TEXT_CELL = "text-[length:var(--text-src-triple)]";
/** Same token as SortableHeader (see `index.css` `--table-header-font-size`). */
const PANEL_TEXT_COL_HEADER = "text-[length:var(--table-header-font-size)]";
/** Dense meta lines (e.g. duration row); scales with `--text-src-triple`. */
const PANEL_TEXT_META = "text-[length:calc(var(--text-src-triple)*0.85)]";

/** Link rows: site badge, title + URL, score %, copy. */
const LINK_ROW_GRID =
  "grid grid-cols-[auto_minmax(0,1fr)_2.75rem_auto] items-start gap-x-2 gap-y-0.5";

/** Raw URL under title (Links panel only). */
const PANEL_TEXT_URL =
  "break-all text-[length:calc(var(--text-src-triple)*0.72)] leading-snug text-muted opacity-90";

/** Set via `SPECIAL_LINK_PREFIX` or `VITE_SPECIAL_LINK_PREFIX` in `.env`; see `vite.config.ts`. */
const SPECIAL_LINK_PREFIX =
  import.meta.env.SPECIAL_LINK_PREFIX || import.meta.env.VITE_SPECIAL_LINK_PREFIX;

/** Shared panel for each link row (best + other). */
const LINK_CARD_CLASS = `rounded-md border-0 bg-neutral-300/80 px-2 py-1.5 ${PANEL_TEXT_CELL} leading-snug dark:bg-neutral-800/85`;

/** Room for bottom-right “mark broken” control. */
const LINK_CARD_WITH_MARK_CLASS = `${LINK_CARD_CLASS} relative pb-7`;

const MARK_BROKEN_BTN_CLASS =
  "absolute bottom-1 right-1 rounded border-0 bg-transparent p-1 text-muted transition-colors hover:bg-surface-2/80 hover:text-red-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50";

/** Matches AppShell “Import playlist CSV” / header actions. */
const HEADER_ACTION_BUTTON_CLASS =
  "inline-flex shrink-0 items-center gap-1 rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-primary hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60";

const WEB_SEARCH_ENGINE_BTN_CLASS = `${HEADER_ACTION_BUTTON_CLASS} gap-0.5 px-1.5 py-0.5`;

const IGNORE_ACTION_STACK_BTN_CLASS = `${HEADER_ACTION_BUTTON_CLASS} w-full justify-start py-1.5 text-left`;

const IGNORE_ACTION_INLINE_BTN_CLASS = `inline-flex shrink-0 items-center rounded border border-border bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60`;

function WebSearchEngineButtons({
  disabled,
  onSelect,
  layout,
  spinTarget,
}: {
  disabled: boolean;
  onSelect: (engine: WebSearchProvider) => void;
  layout: "inline" | "stack";
  spinTarget: LinkSearchSpinTarget;
}) {
  const wrap =
    layout === "stack"
      ? "flex flex-col gap-1.5"
      : "flex shrink-0 flex-wrap items-center justify-end gap-1";
  const googleSpinning = spinTarget === "serper";
  const braveSpinning = spinTarget === "ddg";
  return (
    <div className={wrap}>
      <button
        type="button"
        disabled={disabled}
        className={WEB_SEARCH_ENGINE_BTN_CLASS}
        title="Search with Google (Serper)"
        aria-label="Search links using Google via Serper"
        aria-busy={googleSpinning}
        onClick={() => onSelect("serper")}
      >
        <span>Search</span>
        {googleSpinning ? (
          <HiArrowPath
            className="size-3.5 shrink-0 animate-spin opacity-90"
            aria-hidden
          />
        ) : (
          <SiGoogle className="size-3.5 shrink-0" aria-hidden />
        )}
      </button>
      <button
        type="button"
        disabled={disabled}
        className={WEB_SEARCH_ENGINE_BTN_CLASS}
        title="Search with Brave (ddgs)"
        aria-label="Search links using Brave via ddgs"
        aria-busy={braveSpinning}
        onClick={() => onSelect("ddg")}
      >
        <span>Search</span>
        {braveSpinning ? (
          <HiArrowPath
            className="size-3.5 shrink-0 animate-spin opacity-90"
            aria-hidden
          />
        ) : (
          <SiBrave className="size-3.5 shrink-0" aria-hidden />
        )}
      </button>
    </div>
  );
}

/** One-line label for a purchase/search link (not the raw URL). */
function linkListLabel(
  title: string | null | undefined,
  artist: string | null | undefined,
  fallback: string,
): string {
  const parts = [title?.trim(), artist?.trim()].filter(Boolean);
  return parts.length > 0 ? parts.join(" — ") : fallback;
}

function MarkAmazonLinkBrokenButton({
  disabled,
  onMark,
}: {
  disabled: boolean;
  onMark: () => void;
}) {
  const title = "Mark link as broken";
  return (
    <button
      type="button"
      disabled={disabled}
      title={title}
      aria-label={title}
      onClick={() => void onMark()}
      className={MARK_BROKEN_BTN_CLASS}
    >
      <HiNoSymbol className="size-3.5 shrink-0" aria-hidden />
    </button>
  );
}

function YoutubeDownloadAudioButton({
  disabled,
  onDownload,
}: {
  disabled: boolean;
  onDownload: () => void;
}) {
  const title = "Download as .m4a (AAC) for decks — saves via browser";
  return (
    <button
      type="button"
      disabled={disabled}
      title={title}
      aria-label={title}
      onClick={() => void onDownload()}
      className="shrink-0 rounded border-0 bg-transparent p-1 text-muted transition-colors hover:bg-surface-2/80 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
    >
      <HiArrowDownTray className="size-3.5 shrink-0" aria-hidden />
    </button>
  );
}

function BandcampBuyButton({ url }: { url: string }) {
  const buyUrl = bandcampBuyPageUrl(url);
  const title = "Open Bandcamp buy page (new tab)";
  return (
    <a
      href={buyUrl}
      target="_blank"
      rel="noopener noreferrer"
      title={title}
      aria-label={title}
      className="inline-flex shrink-0 rounded border-0 bg-transparent p-1 text-muted transition-colors hover:bg-surface-2/80 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
    >
      <HiShoppingCart className="size-3.5 shrink-0" aria-hidden />
    </a>
  );
}

function CopyUrlIconButton({
  url,
  copyTitle = "Copy URL",
}: {
  url: string;
  /** Tooltip / aria when not copied (e.g. second button for prefixed link). */
  copyTitle?: string;
}) {
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
      title={copied ? "Copied!" : copyTitle}
      aria-label={
        copied ? "URL copied to clipboard" : `${copyTitle} to clipboard`
      }
      className="shrink-0 rounded border-0 bg-transparent p-1 text-muted transition-colors hover:bg-surface-2/80 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
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
  /** Which engine is running (or ``any`` for full-queue find from toolbar); drives refresh spinners. */
  linkSearchSpinTarget: LinkSearchSpinTarget;
  downloadQueueCount: number;
  onReSearchSelectedDownloads: (engine: WebSearchProvider) => void;
  onPickCandidate: (c: MatchCandidate) => void | Promise<void>;
  onPickTopMatch: () => void | Promise<void>;
  onRejectNoMatch: () => void | Promise<void>;
  onUndoPick: () => void | Promise<void>;
  onUndoReject: () => void | Promise<void>;
  onPickSelectedMatches: () => void | Promise<void>;
  onRejectSelectedMatches: () => void | Promise<void>;
  onWishlistSources: (ids: string[], onWishlist: boolean) => void | Promise<void>;
  /** Download view: mark a purchase/search URL broken (API repoints primary when needed). */
  onMarkAmazonLinkBroken: (url: string) => void | Promise<void>;
  markAmazonLinkBrokenBusy: boolean;
  /** Download view: mark every non-broken best + alternate link for the current selection. */
  onMarkAllShownLinksBroken: () => void | Promise<void>;
  /** Download view: fetch best native audio for a YouTube URL on this row. */
  onDownloadYoutubeAudio: (url: string) => void | Promise<void>;
  youtubeAudioDownloadBusy: boolean;
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
  linkSearchSpinTarget,
  downloadQueueCount,
  onReSearchSelectedDownloads,
  onPickCandidate,
  onPickTopMatch,
  onRejectNoMatch,
  onUndoPick,
  onUndoReject,
  onPickSelectedMatches,
  onRejectSelectedMatches,
  onWishlistSources,
  onMarkAmazonLinkBroken,
  markAmazonLinkBrokenBusy,
  onMarkAllShownLinksBroken,
  onDownloadYoutubeAudio,
  youtubeAudioDownloadBusy,
}: Props) {
  if (mainView === "download") {
    if (sourceSelectionCount === 0) {
      return (
        <PanelChrome title="Links" compactTableStripHeader>
          <p className={`${PANEL_TEXT_CELL} text-muted`}>
            Select a Download row to see the best link and other URLs. Toolbar: Find links opens a
            menu to run a throttled web search (Google via Serper or Brave via ddgs) for every track
            in the queue ({downloadQueueCount}); cached rows are skipped.
          </p>
        </PanelChrome>
      );
    }

    if (sourceSelectionCount > 1) {
      const ignoreable = selectedSourcesBulk.filter((s) => s.on_wishlist);
      const bulkMarkableCount = selectedSourcesBulk.reduce(
        (n, s) => n + collectNonBrokenAmazonLinkUrls(s).length,
        0,
      );
      return (
        <PanelChrome title="Links" compactTableStripHeader>
          <p className={`mb-2 ${PANEL_TEXT_CELL} text-muted`}>
            {sourceSelectionCount} tracks selected
          </p>
          <p className={`mb-3 ${PANEL_TEXT_CELL} text-secondary`}>
            Search (Google) uses Serper; Search (Brave) uses ddgs. Each forces a new web search per
            selected row (delay between requests still applies).
          </p>
          <div className="flex flex-col gap-2">
            <WebSearchEngineButtons
              disabled={findLinksBusy}
              layout="stack"
              spinTarget={linkSearchSpinTarget}
              onSelect={onReSearchSelectedDownloads}
            />
            <button
              type="button"
              disabled={
                findLinksBusy ||
                markAmazonLinkBrokenBusy ||
                bulkMarkableCount === 0
              }
              className={HEADER_ACTION_BUTTON_CLASS}
              title="Mark every non-broken purchase/search link on selected tracks as broken"
              onClick={() => void onMarkAllShownLinksBroken()}
            >
              Mark all links bad {bulkMarkableCount > 0 ? (
                <span className="ml-1 tabular-nums text-muted">({bulkMarkableCount})</span>
              ) : null}
            </button>
            <button
              type="button"
              disabled={wishlistBusy || ignoreable.length === 0}
              className={IGNORE_ACTION_STACK_BTN_CLASS}
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
        <PanelChrome title="Links" compactTableStripHeader>
          <p className={`${PANEL_TEXT_CELL} text-muted`}>Loading selection…</p>
        </PanelChrome>
      );
    }

    const s = selectedSource;
    const candidatesSorted = sortAmazonCandidatesForDisplay(s.amazon_candidates ?? []);
    const bestCand =
      s.amazon_url != null
        ? candidatesSorted.find((c) => c.url === s.amazon_url)
        : undefined;
    const otherLinks =
      s.amazon_url != null
        ? candidatesSorted.filter((c) => c.url !== s.amazon_url)
        : candidatesSorted;
    const searched = s.amazon_last_searched_at != null;
    const specialPrefixedBestUrl =
      SPECIAL_LINK_PREFIX && s.amazon_url
        ? `${SPECIAL_LINK_PREFIX}${s.amazon_url}`
        : "";
    const markableUrls = collectNonBrokenAmazonLinkUrls(s);

    return (
      <PanelChrome
        title="Links"
        compactTableStripHeader
        headerRight={
          <div className="flex max-w-[min(100%,28rem)] flex-wrap items-center justify-end gap-1">
            <button
              type="button"
              disabled={
                findLinksBusy ||
                markAmazonLinkBrokenBusy ||
                markableUrls.length === 0
              }
              className={HEADER_ACTION_BUTTON_CLASS}
              title="Mark every non-broken purchase/search link shown here as broken"
              onClick={() => void onMarkAllShownLinksBroken()}
            >
              Mark all links bad
              {markableUrls.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted">({markableUrls.length})</span>
              ) : null}
            </button>
            <WebSearchEngineButtons
              disabled={findLinksBusy}
              layout="inline"
              spinTarget={linkSearchSpinTarget}
              onSelect={onReSearchSelectedDownloads}
            />
          </div>
        }
      >
        <div
          className={`mb-2 min-w-0 space-y-0.5 text-[length:var(--text-src-triple)]`}
        >
          <div className="font-medium text-primary">{s.title}</div>
          <div className="text-secondary">{s.artist}</div>
        </div>
        <div className={`mb-1 font-medium text-secondary ${PANEL_TEXT_CELL}`}>Best link</div>
        {s.amazon_url ? (
          <div
            className={`${bestCand?.broken ? LINK_CARD_CLASS : LINK_CARD_WITH_MARK_CLASS} mb-3 ${bestCand?.broken ? "opacity-60" : ""}`}
          >
            <div className={LINK_ROW_GRID}>
              <LinkSiteIcon url={s.amazon_url} className="mt-0.5" />
              <div className="min-w-0 space-y-0.5">
                <a
                  href={s.amazon_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`block font-medium leading-snug underline decoration-accent/40 underline-offset-2 hover:decoration-accent ${
                    bestCand?.broken
                      ? "text-muted line-through decoration-muted/50"
                      : "text-accent"
                  }`}
                  title={
                    bestCand?.title?.trim() ||
                    s.amazon_link_title?.trim() ||
                    s.amazon_url
                  }
                >
                  {bestCand?.title?.trim() ||
                    s.amazon_link_title?.trim() ||
                    linkListLabel(null, null, "Open link")}
                </a>
                <div className={PANEL_TEXT_URL}>{s.amazon_url}</div>
              </div>
              <span
                className={`shrink-0 pt-0.5 text-right tabular-nums ${PANEL_TEXT_CELL} text-secondary`}
              >
                {bestCand?.match_score != null || s.amazon_link_match_score != null
                  ? `${Math.round(bestCand?.match_score ?? s.amazon_link_match_score ?? 0)}%`
                  : "—"}
              </span>
              <div className="flex shrink-0 items-center justify-end gap-0.5 pt-0.5">
                {isBandcampUrl(s.amazon_url) && !bestCand?.broken ? (
                  <BandcampBuyButton url={s.amazon_url} />
                ) : null}
                {isYoutubeUrl(s.amazon_url) && !bestCand?.broken ? (
                  <YoutubeDownloadAudioButton
                    disabled={
                      youtubeAudioDownloadBusy ||
                      findLinksBusy ||
                      markAmazonLinkBrokenBusy
                    }
                    onDownload={() => onDownloadYoutubeAudio(s.amazon_url as string)}
                  />
                ) : null}
                <CopyUrlIconButton url={s.amazon_url} />
                {specialPrefixedBestUrl ? (
                  <CopyUrlIconButton
                    url={specialPrefixedBestUrl}
                    copyTitle="Copy prefixed URL"
                  />
                ) : null}
              </div>
            </div>
            {bestCand?.price || s.amazon_price ? (
              <p className="mt-1 tabular-nums text-muted">
                Price: {bestCand?.price ?? s.amazon_price}
              </p>
            ) : null}
            {!bestCand?.broken ? (
              <MarkAmazonLinkBrokenButton
                disabled={markAmazonLinkBrokenBusy || findLinksBusy}
                onMark={() => onMarkAmazonLinkBroken(s.amazon_url as string)}
              />
            ) : null}
          </div>
        ) : searched ? (
          <p className={`mb-3 ${PANEL_TEXT_CELL} text-muted`}>
            No direct link found (search already run).
          </p>
        ) : (
          <p className={`mb-3 ${PANEL_TEXT_CELL} text-muted`}>
            Not searched yet — use Find links.
          </p>
        )}
        <div className={`mb-1 font-medium text-secondary ${PANEL_TEXT_CELL}`}>Other links</div>
        {otherLinks.length === 0 ? (
          <p className={`mt-1 ${PANEL_TEXT_CELL} text-muted`}>
            {searched ? "No alternate URLs." : "Run Find links to populate."}
          </p>
        ) : (
          <ul className="mt-1 space-y-2">
            {otherLinks.map((c, i) => (
              <li
                key={`${c.url}-${i}`}
                className={`${c.broken ? LINK_CARD_CLASS : LINK_CARD_WITH_MARK_CLASS} ${c.broken ? "opacity-60" : ""}`}
              >
                <div className={LINK_ROW_GRID}>
                  <LinkSiteIcon url={c.url} className="mt-0.5" />
                  <div className="min-w-0 space-y-0.5">
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`block font-medium leading-snug underline decoration-accent/40 underline-offset-2 hover:decoration-accent ${
                        c.broken
                          ? "text-muted line-through decoration-muted/50"
                          : "text-accent"
                      }`}
                      title={c.url}
                    >
                      {linkListLabel(c.title, c.artist, "Link")}
                    </a>
                    <div className={PANEL_TEXT_URL}>{c.url}</div>
                  </div>
                  <span className="shrink-0 pt-0.5 text-right tabular-nums text-muted">
                    {c.match_score != null ? `${Math.round(c.match_score)}%` : "—"}
                  </span>
                  <div className="flex shrink-0 items-center justify-end gap-0.5 pt-0.5">
                    {isBandcampUrl(c.url) && !c.broken ? (
                      <BandcampBuyButton url={c.url} />
                    ) : null}
                    {isYoutubeUrl(c.url) && !c.broken ? (
                      <YoutubeDownloadAudioButton
                        disabled={
                          youtubeAudioDownloadBusy ||
                          findLinksBusy ||
                          markAmazonLinkBrokenBusy
                        }
                        onDownload={() => onDownloadYoutubeAudio(c.url)}
                      />
                    ) : null}
                    <CopyUrlIconButton url={c.url} />
                    {SPECIAL_LINK_PREFIX ? (
                      <CopyUrlIconButton
                        url={`${SPECIAL_LINK_PREFIX}${c.url}`}
                        copyTitle="Copy prefixed URL"
                      />
                    ) : null}
                  </div>
                </div>
                {c.price ? (
                  <div className="mt-1 tabular-nums text-muted">{c.price}</div>
                ) : null}
                {!c.broken ? (
                  <MarkAmazonLinkBrokenButton
                    disabled={markAmazonLinkBrokenBusy || findLinksBusy}
                    onMark={() => onMarkAmazonLinkBroken(c.url)}
                  />
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {s.amazon_search_url ? (
          <>
            <div className={`mb-1 mt-3 font-medium text-secondary ${PANEL_TEXT_CELL}`}>
              Web search
            </div>
            <div className={`${LINK_CARD_CLASS} mb-3 flex gap-2`}>
              <LinkSiteIcon url={s.amazon_search_url} className="mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <a
                    href={s.amazon_search_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="min-w-0 flex-1 font-medium leading-snug text-accent underline decoration-accent/40 underline-offset-2"
                  >
                    Web search
                  </a>
                  <CopyUrlIconButton url={s.amazon_search_url} />
                </div>
              </div>
            </div>
          </>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {s.on_wishlist ? (
            <button
              type="button"
              disabled={wishlistBusy}
              className={IGNORE_ACTION_INLINE_BTN_CLASS}
              title="Hide from Sources / Download — not deleting the track"
              onClick={() => onWishlistSources([s.id], false)}
            >
              Ignore
            </button>
          ) : (
            <button
              type="button"
              disabled={wishlistBusy}
              className={`rounded border border-border/80 bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50`}
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
          <p className={`${PANEL_TEXT_CELL} text-muted`}>
            Click a row in the source table to load that track&apos;s best library match and
            candidate list here. Ctrl/Cmd+click to add rows; Shift+click for a range — then bulk
            Match / Missing / Ignore actions appear in this panel.
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
          <p className={`mb-2 ${PANEL_TEXT_CELL} text-muted`}>
            {sourceSelectionCount} tracks selected
          </p>
          <p className={`mb-3 ${PANEL_TEXT_CELL} text-secondary`}>
            Match applies each row&apos;s current best library row (from the table). Rows without a
            candidate, marked Missing, or already matched are skipped.
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              disabled={matchActionBusy || pickable.length === 0}
              className={`rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left ${PANEL_TEXT_CELL} text-primary hover:bg-surface-1 disabled:opacity-50`}
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
              className={`rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left ${PANEL_TEXT_CELL} text-primary hover:bg-surface-1 disabled:opacity-50`}
              onClick={() => void onRejectSelectedMatches()}
            >
              Mark selected as Missing
            </button>
            <button
              type="button"
              disabled={wishlistBusy || ignoreableBulk.length === 0}
              className={IGNORE_ACTION_STACK_BTN_CLASS}
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
              className={`rounded border border-border/80 bg-surface-2 px-2 py-1.5 text-left ${PANEL_TEXT_CELL} text-primary hover:bg-surface-1 disabled:opacity-50`}
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
          <p className={`${PANEL_TEXT_CELL} text-muted`}>Loading selection…</p>
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
      ? "Missing"
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
        <div
          className={`mb-2 min-w-0 space-y-0.5 text-[length:var(--text-src-triple)]`}
        >
          <div className="font-medium text-primary">{selectedSource.title}</div>
          <div className="text-secondary">{selectedSource.artist}</div>
        </div>

        <div
          className={`mb-3 space-y-2 rounded border border-border/70 bg-surface-2/50 px-2 py-2 ${PANEL_TEXT_CELL}`}
        >
          <div className="font-medium text-secondary">{topSectionHeading}</div>
          {rejected ? null : belowMin ? (
            <p className={`${PANEL_TEXT_META} text-muted`}>
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
                    className={`rounded border border-border/80 bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50`}
                    onClick={() => void onPickTopMatch()}
                  >
                    Match
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={matchActionBusy}
                  className={`rounded border border-border/80 bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50`}
                  onClick={() => void onRejectNoMatch()}
                >
                  Missing
                </button>
              </>
            ) : (
              <button
                type="button"
                disabled={matchActionBusy}
                className={`rounded border border-border/80 bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50`}
                onClick={() => void onUndoReject()}
              >
                Undo Missing
              </button>
            )}
            {picked ? (
              <button
                type="button"
                disabled={matchActionBusy}
                className={`rounded border border-border/80 bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50`}
                onClick={() => void onUndoPick()}
              >
                Undo match
              </button>
            ) : null}
            {selectedSource.on_wishlist ? (
              <button
                type="button"
                disabled={matchActionBusy || wishlistBusy}
                className={IGNORE_ACTION_INLINE_BTN_CLASS}
                title="Hide from Sources / Download — not deleting the track"
                onClick={() => onWishlistSources([selectedSource.id], false)}
              >
                Ignore
              </button>
            ) : (
              <button
                type="button"
                disabled={wishlistBusy}
                className={`rounded border border-border/80 bg-surface-1 px-2 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50`}
                onClick={() => onWishlistSources([selectedSource.id], true)}
              >
                Restore to list
              </button>
            )}
          </div>
        </div>

        <div
          className={`${PANEL_TEXT_COL_HEADER} font-medium uppercase tracking-wide text-secondary`}
        >
          Candidates
        </div>
        {candidatesError ? (
          <p className={`mt-1 ${PANEL_TEXT_CELL} text-red-400`}>{candidatesError.message}</p>
        ) : candidatesLoading ? (
          <p className={`mt-1 ${PANEL_TEXT_CELL} text-muted`}>Loading candidates…</p>
        ) : candidatesVisible.length === 0 ? (
          <p className={`mt-1 ${PANEL_TEXT_CELL} text-muted`}>No candidates for this source.</p>
        ) : (
          <ul className="mt-1 space-y-2">
            {candidatesVisible.map((c) => {
              const isCurrent = topId != null && c.id === topId;
              const titleS = c.title_match_score;
              const artistS = c.artist_match_score;
              return (
                <li
                  key={c.id}
                  className={`rounded-md border-0 px-2 py-1.5 ${PANEL_TEXT_CELL} leading-snug ${
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
                      <div className={`mt-1 tabular-nums ${PANEL_TEXT_META} text-muted`}>
                        {formatDurationMs(c.duration_ms)} ·{" "}
                        {c.bpm != null ? `${c.bpm} BPM` : "—"} · {c.musical_key ?? "—"}
                      </div>
                      <button
                        type="button"
                        disabled={matchActionBusy || rejected}
                        className={`mt-1 rounded border border-border/50 bg-surface-1 px-1.5 py-0.5 ${PANEL_TEXT_CELL} text-primary hover:bg-surface-2 disabled:opacity-50 dark:bg-surface-2/80`}
                        onClick={() => void onPickCandidate(c)}
                      >
                        Match
                      </button>
                    </div>
                    <div className={`shrink-0 self-start tabular-nums ${PANEL_TEXT_CELL} font-semibold text-primary`}>
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
        <p className={`${PANEL_TEXT_CELL} text-muted`}>
          Select a library row for path and metadata.
        </p>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Library file">
      <dl className={`space-y-2 ${PANEL_TEXT_CELL}`}>
        <div>
          <dt className="text-muted">Path</dt>
          <dd className={`break-all font-mono ${PANEL_TEXT_CELL} text-secondary`}>
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

function PanelChrome({
  title,
  children,
  headerRight,
  compactTableStripHeader = false,
}: {
  title: string;
  children: React.ReactNode;
  /** Shown on the right (e.g. Redo search); use with ``compactTableStripHeader`` for Links. */
  headerRight?: React.ReactNode;
  /** Links panel: header bar min-height matches primary DataTable thead (topChrome + column headers). */
  compactTableStripHeader?: boolean;
}) {
  if (compactTableStripHeader) {
    return (
      <section
        className="flex h-full min-h-0 flex-col rounded border border-border bg-surface-1"
        aria-label={title}
      >
        <header
          className={`flex min-h-[var(--workspace-primary-thead-height)] shrink-0 items-center gap-2 border-b border-border bg-surface-2 px-[var(--cell-px)] shadow-sm ${
            headerRight ? "justify-between" : ""
          }`}
        >
          <span
            className={`min-w-0 ${PANEL_TEXT_COL_HEADER} font-semibold uppercase tracking-wide text-secondary`}
          >
            {title}
          </span>
          {headerRight}
        </header>
        <div className="min-h-0 flex-1 overflow-auto p-2">{children}</div>
      </section>
    );
  }

  return (
    <section
      className="flex h-full min-h-0 flex-col rounded border border-border bg-surface-1"
      aria-label={title}
    >
      <header
        className={`border-b border-border bg-surface-2 px-2 py-1.5 ${PANEL_TEXT_COL_HEADER} font-semibold uppercase tracking-wide text-secondary`}
      >
        {title}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-2">{children}</div>
    </section>
  );
}
