import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the API so the app always talks to the same origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", sourcemap: false },
});
