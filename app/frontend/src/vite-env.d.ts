/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly BASE_URL: string;
  readonly VITE_STATIC?: string;
  readonly VITE_LIVE_PRICES_URL?: string;
  readonly VITE_LIVE_APP_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
