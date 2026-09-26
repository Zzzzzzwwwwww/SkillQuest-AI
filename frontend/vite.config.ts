/// <reference types="vitest" />
import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

// Vite 配置：https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const proxyTarget =
    env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    // 开发服务器：统一走 5175 端口，避免与常见 5173 冲突
    server: {
      host: "0.0.0.0",
      port: 5175,
      strictPort: false,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          // 后端前缀本身即 /api/v1，无需重写
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
      chunkSizeWarningLimit: 1500,
      rollupOptions: {
        output: {
          manualChunks: {
            "element-plus": ["element-plus"],
            echarts: ["echarts"],
            g6: ["@antv/g6"],
            vue: ["vue", "vue-router", "pinia"],
          },
        },
      },
    },
  };
});