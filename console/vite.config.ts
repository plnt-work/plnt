import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Built into the Python package so `plnt serve` can host it at /console.
// In dev (`npm run dev`), /v1 is proxied to a local `plnt dev` / `plnt serve`.
export default defineConfig({
  base: "/console/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: { outDir: "../plnt/server/console", emptyOutDir: true },
  server: {
    port: 5174,
    proxy: { "/v1": { target: "http://127.0.0.1:8787", changeOrigin: true } },
  },
});
