import { defineConfig, devices } from "@playwright/test";
import { config as loadEnv } from "dotenv";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

// Load a local .env first (developer machine), then fall back to .env.example
// so the env contract is always resolvable — including in CI before any real
// app is wired up. CI / dev pipelines may also inject these via real env vars,
// which take precedence over both files (dotenv does not override existing keys).
const localEnv = resolve(__dirname, ".env");
loadEnv({ path: existsSync(localEnv) ? localEnv : resolve(__dirname, ".env.example") });

// Base URLs the suite targets. Documented in e2e/.env.example.
export const WEB_BASE_URL = process.env.WEB_BASE_URL ?? "http://localhost:3000";
export const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./tests",
  // Glob keeps spec discovery explicit; smoke + future navigation specs both match.
  testMatch: "**/*.spec.ts",
  // Fail the build if someone leaves a `test.only` in a committed spec.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB_BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // NOTE: no `webServer` block yet — Day 1 smoke runs WITHOUT a live server.
  // US-QA-D03 will add `webServer` (spin up web + api) for real navigation specs.
});
