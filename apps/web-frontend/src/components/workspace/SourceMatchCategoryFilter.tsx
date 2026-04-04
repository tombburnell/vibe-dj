import type { SourceMatchCategoryFilterState } from "@/lib/sourceMatchCategory";

type Props = {
  value: SourceMatchCategoryFilterState;
  onChange: (next: SourceMatchCategoryFilterState) => void;
};

const keys: { key: keyof SourceMatchCategoryFilterState; label: string }[] = [
  { key: "picked", label: "Picked" },
  { key: "rejected", label: "Rejected" },
  { key: "uncategorised", label: "Uncategorised" },
];

export function SourceMatchCategoryFilter({ value, onChange }: Props) {
  return (
    <fieldset className="flex flex-wrap items-center gap-x-3 gap-y-1 border-0 p-0 text-[0.75rem] text-secondary">
      <legend className="sr-only">Filter by match status</legend>
      <span className="whitespace-nowrap font-medium text-muted">Match:</span>
      {keys.map(({ key, label }) => (
        <label
          key={key}
          className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap hover:text-primary"
        >
          <input
            type="checkbox"
            className="h-3.5 w-3.5 rounded border-border accent-accent"
            checked={value[key]}
            onChange={(e) =>
              onChange({
                ...value,
                [key]: e.target.checked,
              })
            }
          />
          <span>{label}</span>
        </label>
      ))}
    </fieldset>
  );
}
