import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ChangeEvent } from "react";

import type { LocalScanMatched, LocalScanResult } from "@/api/types";
import { postLocalScan } from "@/api/endpoints";
import { useToast } from "@/providers/ToastProvider";

import { LocalScanModal } from "@/components/settings/LocalScanModal";

const DL_AUDIO_EXT = [".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".wma"] as const;

const LOCAL_SCAN_LOG = "[local-scan]";

function extFromPath(p: string): string {
  const base = p.split("/").pop() ?? p;
  const dot = base.lastIndexOf(".");
  return dot >= 0 ? base.slice(dot).toLowerCase() : "(no ext)";
}

function isAudioRelativePath(path: string): boolean {
  const lower = path.toLowerCase();
  return DL_AUDIO_EXT.some((ext) => lower.endsWith(ext));
}

export type LocalScanFolderTriggerProps = {
  idleLabel: string;
  scanningLabel?: string;
  buttonClassName: string;
};

export function LocalScanFolderTrigger({
  idleLabel,
  scanningLabel = "Scanning…",
  buttonClassName,
}: LocalScanFolderTriggerProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [localScanModalOpen, setLocalScanModalOpen] = useState(false);
  const [localScanPhase, setLocalScanPhase] = useState<"scanning" | "done" | "error">(
    "scanning",
  );
  const [localScanProgress, setLocalScanProgress] = useState<{
    chunkIndex: number;
    chunkCount: number;
  } | null>(null);
  const [localScanTotalAudio, setLocalScanTotalAudio] = useState(0);
  const [localScanResult, setLocalScanResult] = useState<LocalScanResult | null>(null);
  const [localScanError, setLocalScanError] = useState<string | null>(null);

  useEffect(() => {
    if (localScanModalOpen) {
      console.info(LOCAL_SCAN_LOG, "modal state open=true", { phase: localScanPhase });
    }
  }, [localScanModalOpen, localScanPhase]);

  const closeLocalScanModal = () => {
    setLocalScanModalOpen(false);
    setLocalScanProgress(null);
    setLocalScanResult(null);
    setLocalScanError(null);
  };

  const onLocalFolderChange = async (e: ChangeEvent<HTMLInputElement>) => {
    console.info(LOCAL_SCAN_LOG, "input change fired");
    const list = e.target.files ? Array.from(e.target.files) : [];
    e.target.value = "";
    if (!list.length) {
      console.info(LOCAL_SCAN_LOG, "no files on input (length 0 or null)");
      return;
    }
    console.info(LOCAL_SCAN_LOG, "files from folder (recursive)", list.length);
    const paths: string[] = [];
    const extCounts: Record<string, number> = {};
    for (let i = 0; i < list.length; i++) {
      const f = list[i] as File & { webkitRelativePath?: string };
      const rel =
        f.webkitRelativePath && f.webkitRelativePath.length > 0
          ? f.webkitRelativePath
          : f.name;
      const ext = extFromPath(rel);
      extCounts[ext] = (extCounts[ext] ?? 0) + 1;
      if (isAudioRelativePath(rel)) paths.push(rel);
    }
    const sample = Math.min(5, list.length);
    for (let i = 0; i < sample; i++) {
      const f = list[i] as File & { webkitRelativePath?: string };
      console.info(LOCAL_SCAN_LOG, `sample[${i}]`, {
        name: f.name,
        webkitRelativePath: f.webkitRelativePath ?? "(missing)",
      });
    }
    console.info(LOCAL_SCAN_LOG, "extensions in folder (counts)", extCounts);
    console.info(LOCAL_SCAN_LOG, "audio paths kept", paths.length, paths.slice(0, 8));
    if (!paths.length) {
      console.info(
        LOCAL_SCAN_LOG,
        "no paths passed audio filter; allowed:",
        [...DL_AUDIO_EXT].join(", "),
      );
      showToast("No audio files in that folder", "info");
      return;
    }
    console.info(LOCAL_SCAN_LOG, "opening modal, posting scan…");
    setLocalScanModalOpen(true);
    setLocalScanPhase("scanning");
    setLocalScanProgress(null);
    setLocalScanResult(null);
    setLocalScanError(null);
    setLocalScanTotalAudio(paths.length);
    try {
      const r = await postLocalScan(paths, {
        onProgress: (info) =>
          setLocalScanProgress({
            chunkIndex: info.chunkIndex,
            chunkCount: info.chunkCount,
          }),
      });
      const ud = r.unmatched_details ?? [];
      const alreadyHadPath =
        ud.length > 0 ? ud.filter((u) => u.best_source_already_has_file).length : 0;
      const needReview = r.unmatched_files.length - alreadyHadPath;
      console.info(LOCAL_SCAN_LOG, "scan API ok", {
        matched: r.matched.length,
        unmatched: r.unmatched_files.length,
        needReview,
        alreadyHadPath,
        skipped_non_audio: r.skipped_non_audio,
      });
      await queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
      setLocalScanPhase("done");
      setLocalScanResult(r);
      showToast(
        `Local scan: ${r.matched.length} newly matched, ${needReview} unmatched, ${alreadyHadPath} already had a path`,
        "info",
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(LOCAL_SCAN_LOG, "scan API error", msg, err);
      setLocalScanPhase("error");
      setLocalScanError(msg);
      showToast(msg, "error");
    }
  };

  const scanning = localScanModalOpen && localScanPhase === "scanning";

  return (
    <>
      <input
        ref={folderInputRef}
        type="file"
        className="sr-only"
        multiple
        // @ts-expect-error webkitdirectory for folder picker (Chromium, Safari)
        webkitdirectory=""
        onChange={onLocalFolderChange}
      />
      <button
        type="button"
        disabled={scanning}
        className={buttonClassName}
        onClick={() => {
          console.info(LOCAL_SCAN_LOG, "choose folder button click");
          folderInputRef.current?.click();
        }}
      >
        {scanning ? scanningLabel : idleLabel}
      </button>
      <LocalScanModal
        open={localScanModalOpen}
        onClose={closeLocalScanModal}
        phase={localScanPhase}
        totalAudioFiles={localScanTotalAudio}
        progress={localScanProgress}
        result={localScanResult}
        error={localScanError}
        onUnmatchedManuallyMatched={(m: LocalScanMatched) => {
          setLocalScanResult((r) => {
            if (!r) return r;
            return {
              ...r,
              unmatched_files: r.unmatched_files.filter((p) => p !== m.path),
              unmatched_details: (r.unmatched_details ?? []).filter(
                (u) => u.path !== m.path,
              ),
              matched: [...r.matched, m],
            };
          });
          void queryClient.invalidateQueries({ queryKey: ["sourceTracks"] });
        }}
      />
    </>
  );
}
