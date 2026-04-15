/**
 * Low-level HTTP helper — no React.
 * Uses Vite proxy in dev (`/api` → FastAPI) or `VITE_API_BASE_URL`.
 */

const base = (): string => {
  const env = import.meta.env.VITE_API_BASE_URL;
  if (env && env.length > 0) return env.replace(/\/$/, "");
  return "";
};

function devUserHeaders(): HeadersInit {
  const id = import.meta.env.VITE_DEV_USER_ID;
  if (typeof id === "string" && id.trim().length > 0) {
    return { "X-Dev-User-Id": id.trim() };
  }
  return {};
}

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", ...devUserHeaders() },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...devUserHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPutJson<T>(path: string, body: unknown): Promise<T> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...devUserHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "DELETE",
    headers: { Accept: "application/json", ...devUserHeaders() },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
}

export type ApiBlobDownloadResult = {
  blob: Blob;
  filename: string | null;
  persistedPath: string | null;
};

function parseContentDispositionFilename(cd: string | null): string | null {
  if (!cd) return null;
  const star = /filename\*=UTF-8''([^;\s]+)/i.exec(cd);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      return star[1].trim();
    }
  }
  const quoted = /filename="([^"]+)"/i.exec(cd);
  if (quoted) return quoted[1];
  return null;
}

/** POST JSON, expect binary body (e.g. ``audio/mp4``). */
export async function apiPostBlobDownload(
  path: string,
  body: unknown,
): Promise<ApiBlobDownloadResult> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "audio/mp4,application/octet-stream,*/*",
      "Content-Type": "application/json",
      ...devUserHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  const blob = await res.blob();
  const persistedPath = res.headers.get("X-Persisted-Path");
  const filename = parseContentDispositionFilename(res.headers.get("Content-Disposition"));
  return {
    blob,
    filename,
    persistedPath: persistedPath && persistedPath.length > 0 ? persistedPath : null,
  };
}

export async function apiPostFormData<T>(path: string, form: FormData): Promise<T> {
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", ...devUserHeaders() },
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}
