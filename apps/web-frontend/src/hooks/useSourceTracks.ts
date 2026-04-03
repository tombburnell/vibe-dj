import { useCallback } from "react";

import { fetchSourceTracks } from "@/api/endpoints";
import type { SourceTrack } from "@/api/types";
import { useAsyncResource } from "./useAsyncResource";

export function useSourceTracks() {
  const loader = useCallback(() => fetchSourceTracks(), []);
  return useAsyncResource<SourceTrack[]>(loader);
}
