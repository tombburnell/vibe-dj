import clsx from "clsx";
import { Fragment, useEffect, useId } from "react";
import { createPortal } from "react-dom";
import { HiXMark } from "react-icons/hi2";

import { useWelcomeModal } from "@/contexts/WelcomeModalContext";

function FlowDiagramHorizontal() {
  const box =
    "flex min-h-[5.5rem] w-full min-w-0 max-w-[13rem] flex-col justify-center rounded-md border border-border bg-surface-2 px-3 py-2.5 text-center shadow-sm sm:max-w-none sm:flex-1 sm:basis-0";
  const title =
    "text-[0.65rem] font-semibold uppercase tracking-wide text-muted";
  const label = "mt-1 text-[0.8rem] font-medium text-primary leading-snug";

  const steps = [
    { k: "in", title: "In", label: "Playlists & imports" },
    { k: "map", title: "Map", label: "Match to your library" },
    { k: "decide", title: "Decide", label: "Pick, reject, store links" },
    { k: "out", title: "Out", label: "Catalog & download queue" },
  ] as const;

  return (
    <div className="w-full py-2" aria-hidden>
      <p className="mb-4 text-center text-[0.8rem] text-muted">
        External lists → your files & links
      </p>
      <div className="flex flex-col items-center gap-2 sm:flex-row sm:flex-wrap sm:justify-center sm:gap-3 md:flex-nowrap">
        {steps.map((s, i) => (
          <Fragment key={s.k}>
            {i > 0 ? (
              <span
                className="select-none text-lg leading-none text-muted md:px-1"
                aria-hidden
              >
                <span className="sm:hidden">↓</span>
                <span className="hidden sm:inline">→</span>
              </span>
            ) : null}
            <div className={box}>
              <div className={title}>{s.title}</div>
              <div className={label}>{s.label}</div>
            </div>
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function HelpFaq() {
  const items: { q: string; a: string }[] = [
    {
      q: "What is a “source” row?",
      a: "A track from an imported playlist or list. It is the side you are reconciling against your library.",
    },
    {
      q: "Why do matches need confirmation?",
      a: "Same song can appear under different IDs or titles. You approve the right library row or reject bad suggestions.",
    },
    {
      q: "What is the Download view?",
      a: "Tracks you marked missing or want to acquire. Use link search to open store pages, then download locally when ready.",
    },
    {
      q: "Where do imports live?",
      a: "Use Settings for library snapshots, CSV, Spotify, and folder scans. Data stays in this app’s backend.",
    },
  ];

  return (
    <dl className="space-y-4 text-[0.85rem] leading-relaxed">
      {items.map((item) => (
        <div key={item.q}>
          <dt className="font-semibold text-primary">{item.q}</dt>
          <dd className="mt-1 text-secondary">{item.a}</dd>
        </div>
      ))}
    </dl>
  );
}

export function WelcomeModal() {
  const titleId = useId();
  const {
    isOpen,
    activeTab,
    setActiveTab,
    dontShowAgain,
    setDontShowAgain,
    closeWelcomeModal,
  } = useWelcomeModal();

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeWelcomeModal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, closeWelcomeModal]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[210] flex items-center justify-center bg-black/60 p-3 sm:p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) closeWelcomeModal();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex min-h-[80vh] min-w-[80vw] max-h-[calc(100vh-1.5rem)] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-lg border border-border bg-surface-1 shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h2 id={titleId} className="text-[0.9rem] font-semibold text-primary">
            Track Mapper
          </h2>
          <button
            type="button"
            className="shrink-0 rounded p-1.5 text-muted hover:bg-surface-2 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Close"
            onClick={closeWelcomeModal}
          >
            <HiXMark className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div
          className="flex shrink-0 gap-1 border-b border-border bg-surface-1 px-4 py-2"
          role="tablist"
          aria-label="Dialog sections"
        >
          {(
            [
              { id: "welcome" as const, label: "Welcome" },
              { id: "help" as const, label: "Help" },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={activeTab === t.id}
              className={clsx(
                "rounded px-3 py-1 text-[0.75rem] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
                activeTab === t.id
                  ? "bg-surface-2 text-primary"
                  : "text-muted hover:text-secondary",
              )}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {activeTab === "welcome" ? (
            <div className="space-y-4">
              <div className="space-y-2 text-[0.85rem] leading-relaxed text-secondary">
                <p className="text-primary font-medium">Welcome.</p>
                <p>
                  Connect playlist tracks to your library, spot gaps, confirm
                  matches, and queue downloads.
                </p>
              </div>
              <FlowDiagramHorizontal />
            </div>
          ) : (
            <HelpFaq />
          )}
        </div>

        {activeTab === "welcome" ? (
          <div className="flex shrink-0 flex-col gap-3 border-t border-border px-4 py-3">
            <label className="flex cursor-pointer items-start gap-2 text-[0.8rem] text-secondary">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-border accent-accent"
                checked={dontShowAgain}
                onChange={(e) => setDontShowAgain(e.target.checked)}
              />
              <span>Do not show this again</span>
            </label>
            <button
              type="button"
              className="w-full rounded-md border border-accent bg-accent px-3 py-2 text-[0.85rem] font-semibold text-white hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent dark:text-background"
              onClick={closeWelcomeModal}
            >
              Continue
            </button>
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
