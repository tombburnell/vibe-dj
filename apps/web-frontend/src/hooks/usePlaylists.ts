import { useCallback } from "react";

import { fetchPlaylists } from "@/api/endpoints";
import type { Playlist } from "@/api/types";
import { useAsyncResource } from "./useAsyncResource";

export function usePlaylists() {
  const loader = useCallback(() => fetchPlaylists(), []);
  return useAsyncResource<Playlist[]>(loader);
}
