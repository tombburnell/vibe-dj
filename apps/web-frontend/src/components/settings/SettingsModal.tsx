import { useEffect, useId } from "react";
import { createPortal } from "react-dom";
import { HiXMark } from "react-icons/hi2";

import { SettingsPanel } from "@/components/settings/SettingsPanel";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function SettingsModal({ open, onClose }: Props) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[min(92vh,48rem)] w-full max-w-lg flex-col overflow-hidden rounded-lg border border-border bg-surface-1 shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h2 id={titleId} className="text-[0.9rem] font-semibold text-primary">
            Settings
          </h2>
          <button
            type="button"
            className="shrink-0 rounded p-1.5 text-muted hover:bg-surface-2 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Close settings"
            onClick={onClose}
          >
            <HiXMark className="h-5 w-5" aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <SettingsPanel />
        </div>
      </div>
    </div>,
    document.body,
  );
}
