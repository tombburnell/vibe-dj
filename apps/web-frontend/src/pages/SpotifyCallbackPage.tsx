import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { postSpotifyOAuthToken } from "@/api/endpoints";
import { queryKeys } from "@/api/queryKeys";
import {
  clearSpotifyOAuthCallbackSession,
  getSpotifyRedirectUriFallback,
  peekSpotifyOAuthCallbackSession,
} from "@/lib/spotifyOauth";
import { useToast } from "@/providers/ToastProvider";

const CALLBACK_INFLIGHT_KEY = "spotify_oauth_callback_inflight";

export function SpotifyCallbackPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (sessionStorage.getItem(CALLBACK_INFLIGHT_KEY) === "1") {
      return;
    }
    sessionStorage.setItem(CALLBACK_INFLIGHT_KEY, "1");

    void (async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const err = params.get("error");
        const desc = params.get("error_description");
        if (err) {
          clearSpotifyOAuthCallbackSession();
          showToast(desc || err || "Spotify authorization failed", "error");
          navigate("/", { replace: true });
          return;
        }
        const code = params.get("code");
        const state = params.get("state");
        const peeked = peekSpotifyOAuthCallbackSession();
        if (!code || !state || !peeked || state !== peeked.state) {
          clearSpotifyOAuthCallbackSession();
          showToast("Invalid or expired Spotify login session. Try Connect again.", "error");
          navigate("/", { replace: true });
          return;
        }
        const redirectUsed =
          peeked.redirectUri.length > 0
            ? peeked.redirectUri
            : getSpotifyRedirectUriFallback();
        try {
          await postSpotifyOAuthToken({
            code,
            code_verifier: peeked.verifier,
            redirect_uri: redirectUsed,
          });
          void queryClient.invalidateQueries({ queryKey: queryKeys.spotifyOAuthStatus });
          showToast("Spotify connected.", "info");
        } catch (e) {
          showToast(e instanceof Error ? e.message : String(e), "error");
        } finally {
          clearSpotifyOAuthCallbackSession();
        }
        navigate("/", { replace: true });
      } finally {
        sessionStorage.removeItem(CALLBACK_INFLIGHT_KEY);
      }
    })();
  }, [navigate, queryClient, showToast]);

  return (
    <div className="flex min-h-[40vh] items-center justify-center p-6 text-[0.9rem] text-primary">
      Finishing Spotify login…
    </div>
  );
}
