/// <reference types="vite/client" />

// Hằng số thay lúc build (vite.config define) — version lấy từ package.json.
declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
