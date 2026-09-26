/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端 API 基础地址 */
  readonly VITE_API_BASE?: string;
  /** 应用标题 */
  readonly VITE_APP_TITLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>;
  export default component;
}