import { Link } from "react-router-dom";

import { useDensity } from "@/hooks/useDensity";
import { useTheme } from "@/hooks/useTheme";

import { DensitySelect } from "./DensitySelect";

export function AppHeader() {
  const { theme, toggle } = useTheme();
  const { density, setDensity } = useDensity();

  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-surface-2 px-3">
      <div className="flex items-center gap-4">
        <Link
          to="/"
          className="text-[0.875rem] font-semibold tracking-tight text-primary hover:text-accent"
        >
          Track Mapper
        </Link>
        <nav className="flex gap-2 text-[0.75rem]" aria-label="Main">
          <Link
            to="/"
            className="text-secondary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Workspace
          </Link>
          <Link
            to="/settings"
            className="text-secondary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Settings
          </Link>
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <DensitySelect value={density} onChange={setDensity} />
        <button
          type="button"
          className="rounded border border-border bg-surface-1 px-2 py-1 text-[0.75rem] text-secondary hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          onClick={toggle}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </div>
    </header>
  );
}
