import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  disconnectSpotifyOAuth,
  fetchSpotifyOAuthConfig,
  fetchSpotifyOAuthStatus,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryKeys";
import { buildSpotifyAuthorizeUrl } from "@/lib/spotifyOauth";
import { useToast } from "@/providers/ToastProvider";

export function SpotifyConnectionPanel() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [connectBusy, setConnectBusy] = useState(false);

  const statusQuery = useQuery({
    queryKey: queryKeys.spotifyOAuthStatus,
    queryFn: fetchSpotifyOAuthStatus,
    staleTime: 60_000,
  });

  const connected = statusQuery.data?.connected === true;

  const disconnectMutation = useMutation({
    mutationFn: () => disconnectSpotifyOAuth(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spotifyOAuthStatus });
      showToast("Spotify disconnected.", "info");
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : String(err), "error");
    },
  });

  return (
    <section className="space-y-3 rounded border border-border bg-surface-1 p-4">
      <h2 className="text-[0.8rem] font-medium text-secondary">Spotify</h2>
      <p className="text-[0.75rem] text-muted">
        Connect your Spotify account to import playlists from Spotify on the workspace. You can
        disconnect anytime; imported catalog data stays in the app.
      </p>
      {statusQuery.isLoading ? (
        <p className="text-[0.75rem] text-muted">Checking connection…</p>
      ) : statusQuery.error ? (
        <p className="text-[0.75rem] text-red-400">{statusQuery.error.message}</p>
      ) : !connected ? (
        <button
          type="button"
          disabled={connectBusy}
          title="Log in with Spotify to import playlists"
          className="rounded border border-border bg-surface-2 px-3 py-1.5 text-[0.8125rem] text-primary hover:bg-surface-1 disabled:cursor-wait disabled:opacity-70"
          onClick={() => {
            void (async () => {
              setConnectBusy(true);
              try {
                const cfg = await fetchSpotifyOAuthConfig();
                window.location.assign(await buildSpotifyAuthorizeUrl(cfg));
              } catch (e) {
                setConnectBusy(false);
                showToast(e instanceof Error ? e.message : String(e), "error");
              }
            })();
          }}
        >
          {connectBusy ? "Connecting…" : "Connect Spotify"}
        </button>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <span
            className="text-[0.8125rem] text-primary"
            title={statusQuery.data?.spotify_user_id ?? "Connected"}
          >
            Linked
            {statusQuery.data?.spotify_user_id ? (
              <span className="text-secondary"> · {statusQuery.data.spotify_user_id}</span>
            ) : null}
          </span>
          <button
            type="button"
            disabled={disconnectMutation.isPending}
            className="rounded border border-border bg-surface-2 px-3 py-1.5 text-[0.8125rem] text-primary hover:bg-surface-1 disabled:opacity-60"
            onClick={() => disconnectMutation.mutate()}
          >
            {disconnectMutation.isPending ? "Disconnecting…" : "Disconnect Spotify"}
          </button>
        </div>
      )}
    </section>
  );
}
