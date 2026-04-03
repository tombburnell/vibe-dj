import { useCallback } from "react";

import { fetchLibraryTracks } from "@/api/endpoints";
import type { LibraryTrack } from "@/api/types";
import { useAsyncResource } from "./useAsyncResource";

export function useLibraryTracks() {
  const loader = useCallback(() => fetchLibraryTracks(), []);
  return useAsyncResource<LibraryTrack[]>(loader);
}
