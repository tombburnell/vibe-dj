import { useCallback, useState } from "react";

const STORAGE_KEY = "track-mapper-ui-scale";

function readStored(): number {
  if (typeof localStorage === "undefined") return 100;
  const s = localStorage.getItem(STORAGE_KEY);
  const n = s ? parseFloat(s) : 100;
  return Number.isFinite(n) && n >= 80 && n <= 140 ? n : 100;
}

export function useUiScale() {
  const [percent, setPercentState] = useState(readStored);

  const setPercent = useCallback((n: number) => {
    const clamped = Math.min(140, Math.max(80, n));
    setPercentState(clamped);
    document.documentElement.style.fontSize = `${clamped}%`;
    localStorage.setItem(STORAGE_KEY, String(clamped));
  }, []);

  return { percent, setPercent };
}
