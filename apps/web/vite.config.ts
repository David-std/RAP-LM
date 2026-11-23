/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // During development the SPA calls the API through the same origin.
    proxy: { "/api": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" },
  },
  test: {
    include: ["src/**/*.test.ts"], // e2e/ is run by Playwright, not Vitest
  },
});
