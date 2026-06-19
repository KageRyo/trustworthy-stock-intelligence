import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiTarget = process.env.TSI_DASHBOARD_API_BASE_URL ?? "http://127.0.0.1:18080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true
      },
      "/health": {
        target: apiTarget,
        changeOrigin: true
      }
    }
  }
});
