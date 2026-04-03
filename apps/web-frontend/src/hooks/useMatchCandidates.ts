import { useMemo } from "react";

import type { LibraryTrack } from "@/api/types";
import type { SourceTrack } from "@/api/types";

/**
 * Until `GET /api/source-tracks/:id/candidates` exists, rank library rows client-side
 * for the secondary panel (demo heuristic).
 */
export function useMatchCandidates(
  selected: SourceTrack | null,
  library: LibraryTrack[] | null,
): LibraryTrack[] {
  return useMemo(() => {
    if (!selected || !library?.length) return [];
    const title = selected.title.toLowerCase();
    const artist = selected.artist.toLowerCase();
    const scored = library.map((lib) => {
      let score = 0;
      if (lib.artist.toLowerCase() === artist) score += 3;
      else if (lib.artist.toLowerCase().includes(artist.split(" ")[0] ?? "")) score += 1;
      if (lib.title.toLowerCase().includes(title.slice(0, Math.min(title.length, 12))))
        score += 2;
      if (lib.title.toLowerCase() === title) score += 2;
      return { lib, score };
    });
    return scored
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((x) => x.lib);
  }, [selected, library]);
}
