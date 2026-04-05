import type { Density } from "@/hooks/useDensity";

type Props = {
  value: Density;
  onChange: (d: Density) => void;
};

const options: { value: Density; label: string }[] = [
  { value: "ultra-compact", label: "Ultra" },
  { value: "compact", label: "Compact" },
  { value: "comfortable", label: "Comfort" },
];

export function DensitySelect({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-1.5 text-[0.75rem] text-secondary">
      <span className="sr-only">Table density</span>
      <select
        className="rounded border-0 bg-surface-1 px-2 py-1 text-[0.75rem] text-primary outline-none ring-0 focus:ring-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        value={value}
        onChange={(e) => {
          const v = e.target.value;
          if (v === "comfortable" || v === "compact" || v === "ultra-compact") onChange(v);
        }}
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
