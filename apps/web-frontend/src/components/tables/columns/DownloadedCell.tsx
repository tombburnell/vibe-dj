import { useMutation, useQueryClient } from "@tanstack/react-query";

import { clearSourceTrackLocalFile, setSourceTrackManualDl } from "@/api/endpoints";
import type { SourceTrack } from "@/api/types";
import { useToast } from "@/providers/ToastProvider";

type Props = {
  row: { original: SourceTrack };
};

export function DownloadedCell({ row }: Props) {
  const source = row.original;
  const path = source.local_file_path;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const clearMut = useMutation({
    mutationFn: () => clearSourceTrackLocalFile(source.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      showToast("Cleared local file link", "info");
    },
    onError: (e: Error) => showToast(e.message, "error"),
  });

  const toggleManualMut = useMutation({
    mutationFn: (manualDl: boolean) => setSourceTrackManualDl(source.id, manualDl),
    onMutate: async (manualDl: boolean) => {
      const previous = queryClient.getQueriesData<SourceTrack[]>({
        queryKey: ["sourceTracks"],
      });
      queryClient.setQueriesData<SourceTrack[]>(
        { queryKey: ["sourceTracks"] },
        (rows) =>
          rows?.map((item) =>
            item.id === source.id ? { ...item, manual_dl: manualDl } : item,
          ) ?? rows,
      );
      return { previous };
    },
    onSuccess: (result) => {
      queryClient.setQueriesData<SourceTrack[]>(
        { queryKey: ["sourceTracks"] },
        (rows) =>
          rows?.map((item) =>
            item.id === source.id ? { ...item, manual_dl: result.manual_dl } : item,
          ) ?? rows,
      );
    },
    onError: (e: Error, _manualDl, context) => {
      for (const [key, rows] of context?.previous ?? []) {
        queryClient.setQueryData(key, rows);
      }
      showToast(e.message, "error");
    },
  });

  if (!path) {
    const checked = source.manual_dl;
    return (
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        aria-label={checked ? "Marked downloaded" : "Mark downloaded"}
        disabled={toggleManualMut.isPending}
        className={`inline-flex h-4 w-4 items-center justify-center rounded border text-[0.7rem] leading-none transition-colors disabled:opacity-50 ${
          checked
            ? "border-accent bg-accent text-white dark:text-background"
            : "border-border bg-surface-2 text-muted/60 hover:bg-surface-1"
        }`}
        onClick={(e) => {
          e.stopPropagation();
          toggleManualMut.mutate(!checked);
        }}
      >
        ✓
      </button>
    );
  }

  return (
    <span className="flex flex-nowrap items-center gap-1 whitespace-nowrap">
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
