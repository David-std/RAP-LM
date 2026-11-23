// Critical end-to-end journeys (HT-12, RV-02, M-07) against the deployed stack:
//   docker compose up -d --build && npm run e2e
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8088", viewport: { width: 1440, height: 900 } },
  reporter: [["list"], ["json", { outputFile: "../../evidence/e2e/results.json" }]],
});
