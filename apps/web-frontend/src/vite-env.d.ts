/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  /** Injected in `vite.config.ts` from `SPECIAL_LINK_PREFIX` or `VITE_SPECIAL_LINK_PREFIX`. */
  readonly SPECIAL_LINK_PREFIX: string;
  readonly VITE_SPECIAL_LINK_PREFIX: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
