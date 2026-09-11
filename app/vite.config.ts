import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend build → dist/, served by the Fastify process in production.
// In dev, /api/* is proxied to the backend on port 8000.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
