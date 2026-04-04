import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { deletePlaylist } from "@/api/endpoints";
import { AppShell } from "@/components/layout/AppShell";
import { useDensity } from "@/hooks/useDensity";
import { usePlaylists } from "@/hooks/usePlaylists";
import { useTheme } from "@/hooks/useTheme";
import { useUiScale } from "@/hooks/useUiScale";
import { useToast } from "@/providers/ToastProvider";

import { DensitySelect } from "@/components/layout/DensitySelect";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();
  const { density, setDensity } = useDensity();
  const { percent, setPercent } = useUiScale();
  const { showToast } = useToast();
  const playlistsQuery = usePlaylists();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const deletePlaylistMutation = useMutation({
    mutationFn: (playlistId: string) => deletePlaylist(playlistId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.playlists });
      await queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
    },
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-lg space-y-6 p-4">
        <Link
          to="/"
          className="text-[0.75rem] text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          ← Workspace
        </Link>
        <h1 className="text-lg font-semibold text-primary">Settings</h1>
        <section className="space-y-3 rounded border border-border bg-surface-1 p-4">
          <h2 className="text-[0.8rem] font-medium text-secondary">Appearance</h2>
          <label className="flex items-center justify-between gap-4 text-[0.8125rem] text-primary">
            Theme
            <select
              className="rounded border border-border bg-surface-2 px-2 py-1"
              value={theme}
              onChange={(e) => setTheme(e.target.value as "dark" | "light")}
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </label>
          <label className="flex items-center justify-between gap-4 text-[0.8125rem] text-primary">
            Table density
            <DensitySelect value={density} onChange={setDensity} />
          </label>
          <label className="block text-[0.8125rem] text-primary">
            UI font scale ({percent}%)
            <input
              type="range"
              min={80}
              max={140}
              step={1}
              value={percent}
              onChange={(e) => setPercent(Number(e.target.value))}
              className="mt-1 w-full accent-accent"
            />
          </label>
        </section>

        <section className="space-y-3 rounded border border-border bg-surface-1 p-4">
          <h2 className="text-[0.8rem] font-medium text-secondary">Playlists</h2>
          <p className="text-[0.75rem] text-muted">
            Deleting a playlist removes it from the catalog and unlinks it from every
            source track (tracks themselves are not deleted).
          </p>
          {playlistsQuery.isLoading ? (
            <p className="text-[0.75rem] text-muted">Loading…</p>
          ) : playlistsQuery.error ? (
            <p className="text-[0.75rem] text-red-400">
              {playlistsQuery.error.message}
            </p>
          ) : (playlistsQuery.data ?? []).length === 0 ? (
            <p className="text-[0.75rem] text-muted">No playlists imported yet.</p>
          ) : (
            <ul className="divide-y divide-border rounded border border-border bg-surface-2">
              {(playlistsQuery.data ?? []).map((p) => (
                <li
                  key={p.id}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-[0.8125rem]"
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium text-primary">{p.name}</div>
                    <div className="text-[0.7rem] text-muted">
                      {p.import_source ?? "—"} ·{" "}
                      {new Date(p.created_at).toLocaleString()}
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={deletingId === p.id}
                    className="shrink-0 rounded border border-red-900/60 bg-surface-1 px-2 py-1 text-[0.7rem] text-red-400 hover:bg-red-950/40 disabled:opacity-50"
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `Delete playlist “${p.name}” and remove it from all source tracks?`,
                        )
                      ) {
                        return;
                      }
                      setDeletingId(p.id);
                      try {
                        await deletePlaylistMutation.mutateAsync(p.id);
                        showToast(`Deleted playlist “${p.name}”`, "info");
                      } catch (e) {
                        showToast(
                          e instanceof Error ? e.message : String(e),
                          "error",
                        );
                      } finally {
                        setDeletingId(null);
                      }
                    }}
                  >
                    {deletingId === p.id ? "…" : "Delete"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <p className="text-[0.75rem] text-muted">
          Auth (Firebase) will gate the app later; settings are local for now.
        </p>
      </div>
    </AppShell>
  );
}
