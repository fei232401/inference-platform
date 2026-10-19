import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_TARGET = process.env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000";
const ROUTER_TARGET = process.env.VITE_DEV_ROUTER_TARGET ?? "http://127.0.0.1:8001";
const BUILD_VERSION = process.env.VITE_BUILD_VERSION ?? "dev";

export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_VERSION__: JSON.stringify(BUILD_VERSION),
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/v1": { target: ROUTER_TARGET, changeOrigin: true },
      "/api": { target: API_TARGET, changeOrigin: true },
      "/healthz": { target: API_TARGET, changeOrigin: true },
      "/readyz": { target: API_TARGET, changeOrigin: true },
      "/openapi.json": { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
