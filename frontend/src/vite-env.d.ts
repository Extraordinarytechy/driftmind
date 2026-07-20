/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATA_MODE?: "demo" | "live";
  readonly VITE_REPORT_SOURCE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}