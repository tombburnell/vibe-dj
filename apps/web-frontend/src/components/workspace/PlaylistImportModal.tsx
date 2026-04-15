import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { HiArrowPath, HiXMark } from "react-icons/hi2";

type PlaylistImportModalProps = {
  open: boolean;
  onClose: () => void;
  spotifyConnected: boolean;
  spotifyPlaylistInput: string;
  onSpotifyPlaylistInputChange: (value: string) => void;
  importPlaylistCsvBusy: boolean;
  importSpotifyPlaylistBusy: boolean;
  onImportPlaylistCsv: (file: File) => void;
  onImportSpotifyPlaylist: () => void;
  spotifyPlaylistCount: number;
  syncExistingPlaylistsBusy: boolean;
  syncProgressLabel: string | null;
  syncProgressDetail: string | null;
  onSyncExistingPlaylists: () => void;
};

export function PlaylistImportModal({
  open,
  onClose,
  spotifyConnected,
  spotifyPlaylistInput,
  onSpotifyPlaylistInputChange,
  importPlaylistCsvBusy,
  importSpotifyPlaylistBusy,
  onImportPlaylistCsv,
  onImportSpotifyPlaylist,
  spotifyPlaylistCount,
  syncExistingPlaylistsBusy,
  syncProgressLabel,
  syncProgressDetail,
  onSyncExistingPlaylists,
}: PlaylistImportModalProps) {
  const titleId = useId();
  const playlistFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  const spotifyImportDisabled =
    !spotifyConnected || !spotifyPlaylistInput.trim() || importSpotifyPlaylistBusy;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex w-full max-w-lg flex-col overflow-hidden rounded-lg border border-border bg-surface-1 shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h2 id={titleId} className="text-[0.9rem] font-semibold text-primary">
            Import playlist
          </h2>
          <button
            type="button"
            className="shrink-0 rounded p-1.5 text-muted hover:bg-surface-2 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Close import playlist dialog"
            onClick={onClose}
          >
            <HiXMark className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div className="flex flex-col gap-4 p-4">
          <section className="space-y-2">
            <div>
              <h3 className="text-[0.8rem] font-medium text-primary">Import playlist CSV</h3>
              <p className="mt-1 text-[0.75rem] text-muted">
                Import a playlist export and link any new source tracks.
              </p>
            </div>
            <input
              ref={playlistFileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                onImportPlaylistCsv(file);
              }}
            />
            <button
              type="button"
              disabled={importPlaylistCsvBusy}
              className="inline-flex items-center gap-1.5 rounded border border-border bg-surface-2 px-3 py-2 text-[0.75rem] text-primary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => playlistFileRef.current?.click()}
            >
              {importPlaylistCsvBusy ? (
                <>
                  <HiArrowPath className="size-4 animate-spin" aria-hidden />
                  <span>Importing CSV…</span>
                </>
              ) : (
                "Import playlist CSV"
              )}
            </button>
          </section>

          <section className="space-y-2">
            <div>
              <h3 className="text-[0.8rem] font-medium text-primary">Spotify playlist</h3>
              <p className="mt-1 text-[0.75rem] text-muted">
                Paste a Spotify playlist URL or id and import it into the workspace.
              </p>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={spotifyPlaylistInput}
                onChange={(e) => onSpotifyPlaylistInputChange(e.target.value)}
                placeholder="Spotify playlist URL/id"
                aria-label="Spotify playlist URL or id"
                className="min-w-0 flex-1 rounded border border-border bg-surface-1 px-3 py-2 text-[0.75rem] text-primary outline-none placeholder:text-secondary"
                disabled={!spotifyConnected || importSpotifyPlaylistBusy}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !spotifyImportDisabled) {
                    onImportSpotifyPlaylist();
                  }
                }}
              />
              <button
                type="button"
                disabled={spotifyImportDisabled}
                className="shrink-0 rounded border border-border bg-surface-2 px-3 py-2 text-[0.75rem] text-primary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={onImportSpotifyPlaylist}
              >
                {importSpotifyPlaylistBusy ? "Importing…" : "Import"}
              </button>
            </div>
            {!spotifyConnected ? (
              <p className="text-[0.75rem] text-muted">
                Connect Spotify in the header first, then import by URL.
              </p>
            ) : null}
          </section>

          <section className="space-y-2">
            <div>
              <h3 className="text-[0.8rem] font-medium text-primary">Sync existing playlists</h3>
              <p className="mt-1 text-[0.75rem] text-muted">
                Re-import all saved Spotify playlists and add any newly found tracks.
              </p>
            </div>
            <button
              type="button"
              disabled={syncExistingPlaylistsBusy || spotifyPlaylistCount === 0}
              className="inline-flex items-center gap-1.5 rounded border border-border bg-surface-2 px-3 py-2 text-[0.75rem] text-primary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={onSyncExistingPlaylists}
            >
              {syncExistingPlaylistsBusy ? (
                <>
                  <HiArrowPath className="size-4 animate-spin" aria-hidden />
                  <span>Syncing…</span>
                </>
              ) : (
                "Sync Existing Playlists"
              )}
            </button>
            <p className="text-[0.75rem] text-muted">
              {spotifyPlaylistCount === 0
                ? "No Spotify-imported playlists saved yet."
                : `${spotifyPlaylistCount} Spotify playlist${spotifyPlaylistCount === 1 ? "" : "s"} ready to sync.`}
            </p>
            {syncProgressLabel ? (
              <div className="rounded border border-border bg-surface-2/60 px-3 py-2 text-[0.75rem]">
                <div className="font-medium text-primary">{syncProgressLabel}</div>
                {syncProgressDetail ? (
                  <div className="mt-1 text-secondary">{syncProgressDetail}</div>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>,
    document.body,
  );
}
