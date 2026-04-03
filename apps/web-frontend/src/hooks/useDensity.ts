import { useCallback, useSyncExternalStore } from "react";

export type Density = "comfortable" | "compact" | "ultra-compact";

const STORAGE_KEY = "track-mapper-density";

function readDensity(): Density {
  if (typeof document === "undefined") return "compact";
  const d = document.documentElement.getAttribute("data-density");
  if (d === "comfortable" || d === "compact" || d === "ultra-compact") return d;
  return "compact";
}

function subscribe(onChange: () => void) {
  const obs = new MutationObserver(onChange);
  obs.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-density"],
  });
  return () => obs.disconnect();
}

export function useDensity() {
  const density = useSyncExternalStore<Density>(
    subscribe,
    readDensity,
    (): Density => "compact",
  );

  const setDensity = useCallback((next: Density) => {
    document.documentElement.setAttribute("data-density", next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  return { density, setDensity };
}
