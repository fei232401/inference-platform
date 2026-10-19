import { defineConfig, chromium } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  reporter: "list",
  use: { baseURL: process.env.BROWSER_BASE_URL ?? "http://127.0.0.1:15173", headless: true, launchOptions: { executablePath: chromium.executablePath() } },
});
