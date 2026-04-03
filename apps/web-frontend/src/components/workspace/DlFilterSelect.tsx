export type DlFilter = "all" | "downloaded" | "not_downloaded";

type Props = {
  value: DlFilter;
  onChange: (v: DlFilter) => void;
};

const options: { value: DlFilter; label: string }[] = [
  { value: "all", label: "DL: All" },
  { value: "downloaded", label: "DL: Yes" },
  { value: "not_downloaded", label: "DL: No" },
];

export function DlFilterSelect({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-1.5 text-[0.75rem] text-secondary">
      <span className="sr-only">Filter by downloaded</span>
      <select
        className="rounded border border-border bg-surface-1 px-1.5 py-1 text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        value={value}
        onChange={(e) => onChange(e.target.value as DlFilter)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
