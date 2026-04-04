import { useMutation, useQueryClient } from "@tanstack/react-query";

import { clearSourceTrackLocalFile } from "@/api/endpoints";
import type { SourceTrack } from "@/api/types";
import { useToast } from "@/providers/ToastProvider";

type Props = {
  row: { original: SourceTrack };
};

export function DownloadedCell({ row }: Props) {
  const path = row.original.local_file_path;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const clearMut = useMutation({
    mutationFn: () => clearSourceTrackLocalFile(row.original.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      showToast("Cleared local file link", "info");
    },
    onError: (e: Error) => showToast(e.message, "error"),
  });

  if (!path) {
    return <span className="text-muted">—</span>;
  }

  return (
    <span className="flex flex-wrap items-center gap-1">
      <span className="text-primary" title={path}>
        ✓
      </span>
      <button
        type="button"
        disabled={clearMut.isPending}
        className="rounded border border-border px-1 py-px text-[0.65rem] text-muted hover:bg-surface-2 hover:text-primary disabled:opacity-50"
        onClick={(e) => {
          e.stopPropagation();
          clearMut.mutate();
        }}
      >
        Clear
      </button>
    </span>
  );
}
