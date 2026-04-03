import { Link } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { useDensity } from "@/hooks/useDensity";
import { useTheme } from "@/hooks/useTheme";
import { useUiScale } from "@/hooks/useUiScale";

import { DensitySelect } from "@/components/layout/DensitySelect";

export function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { density, setDensity } = useDensity();
  const { percent, setPercent } = useUiScale();

  return (
    <AppShell>
      <div className="mx-auto max-w-lg space-y-6 p-4">
        <Link
          to="/"
          className="text-[0.75rem] text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          ← Workspace
        </Link>
        <h1 className="text-lg font-semibold text-primary">Settings</h1>
        <section className="space-y-3 rounded border border-border bg-surface-1 p-4">
          <h2 className="text-[0.8rem] font-medium text-secondary">Appearance</h2>
          <label className="flex items-center justify-between gap-4 text-[0.8125rem] text-primary">
            Theme
            <select
              className="rounded border border-border bg-surface-2 px-2 py-1"
              value={theme}
              onChange={(e) => setTheme(e.target.value as "dark" | "light")}
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </label>
          <label className="flex items-center justify-between gap-4 text-[0.8125rem] text-primary">
            Table density
            <DensitySelect value={density} onChange={setDensity} />
          </label>
          <label className="block text-[0.8125rem] text-primary">
            UI font scale ({percent}%)
            <input
              type="range"
              min={80}
              max={140}
              step={1}
              value={percent}
              onChange={(e) => setPercent(Number(e.target.value))}
              className="mt-1 w-full accent-accent"
            />
          </label>
        </section>
        <p className="text-[0.75rem] text-muted">
          Auth (Firebase) will gate the app later; settings are local for now.
        </p>
      </div>
    </AppShell>
  );
}
