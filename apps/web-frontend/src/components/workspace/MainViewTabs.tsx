import clsx from "clsx";

export type MainView = "sources" | "library";

type Props = {
  value: MainView;
  onChange: (v: MainView) => void;
};

const tabs: { id: MainView; label: string }[] = [
  { id: "sources", label: "Sources" },
  { id: "library", label: "Library" },
];

export function MainViewTabs({ value, onChange }: Props) {
  return (
    <div
      className="flex gap-1 rounded-md border border-border bg-surface-1 p-0.5"
      role="tablist"
      aria-label="Main data view"
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          className={clsx(
            "rounded px-3 py-1 text-[0.75rem] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
            value === t.id
              ? "bg-surface-2 text-primary"
              : "text-muted hover:text-secondary",
          )}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
