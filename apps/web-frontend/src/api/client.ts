/**
 * Low-level HTTP helper — no React.
 * Uses Vite proxy in dev (`/api` → FastAPI) or `VITE_API_BASE_URL`.
 */

const base = (): string => {
  const env = import.meta.env.VITE_API_BASE_URL;
  if (env && env.length > 0) return env.replace(/\/$/, "");
  return "";
};

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}
