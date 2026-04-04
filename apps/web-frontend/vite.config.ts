import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Minimal `.env` parse (comments + KEY=value); avoids relying on loadEnv order vs `process.env`. */
function parseEnvSource(src: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of src.split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq <= 0) continue;
    const key = t.slice(0, eq).trim();
    let val = t.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function readSpecialLinkPrefixFromEnvFiles(mode: string, dirs: string[]): string {
  const names = [".env", ".env.local", `.env.${mode}`, `.env.${mode}.local`];
  const merged: Record<string, string> = {};
  for (const dir of dirs) {
    for (const name of names) {
      const p = path.join(dir, name);
      try {
        Object.assign(merged, parseEnvSource(fs.readFileSync(p, "utf8")));
      } catch {
        /* missing or unreadable */
      }
    }
  }
  return (
    merged.SPECIAL_LINK_PREFIX ??
    merged.VITE_SPECIAL_LINK_PREFIX ??
    ""
  ).trim();
}

/** In Docker, set to `http://api:8000` so the Vite dev server can reach the API container. */
const apiProxyTarget =
  process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig(({ mode }) => {
  const root = __dirname;
  const repoRoot = path.resolve(root, "..", "..");

  const fromProcess = (
    process.env.SPECIAL_LINK_PREFIX ??
    process.env.VITE_SPECIAL_LINK_PREFIX ??
    ""
  ).trim();
  const fromFiles = readSpecialLinkPrefixFromEnvFiles(mode, [repoRoot, root]);
  const specialLinkPrefix = fromProcess || fromFiles;

  return {
    plugins: [react()],
    define: {
      "import.meta.env.SPECIAL_LINK_PREFIX": JSON.stringify(specialLinkPrefix),
      "import.meta.env.VITE_SPECIAL_LINK_PREFIX": JSON.stringify(specialLinkPrefix),
    },
    resolve: {
      alias: {
        "@": path.resolve(root, "src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
