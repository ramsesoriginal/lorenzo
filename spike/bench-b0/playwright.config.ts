import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  workers: 1, // one stub server, one world
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:4173", launchOptions: { executablePath: process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium" } },
  webServer: { command: "node scripts/server.mjs", url: "http://127.0.0.1:4173/api/_test/log", reuseExistingServer: false },
});
