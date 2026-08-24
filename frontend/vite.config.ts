import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const outDir =
  process.env.OUT_DIR ||
  (process.env.BUILD_TARGET === "backend" ? "../backend/static" : "dist");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir,
    emptyOutDir: true,
  },
});
