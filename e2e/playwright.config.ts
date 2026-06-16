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

// Base URLs the suite targets. Documented in e2e/.env.example. The live lane
// boots on its own port (3200) so it can run alongside the @web build (3100).
// In the live lane we IGNORE any `.env` WEB_BASE_URL (which pins 3100 for @web)
// and force 3200 — the live lane owns its own self-booted `next dev`.
const LIVE_LANE = !!process.env.E2E_LIVE;
export const WEB_BASE_URL = LIVE_LANE
  ? "http://localhost:3200"
  : (process.env.WEB_BASE_URL ?? "http://localhost:3100");
export const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

// The web app under test. Pinned away from the dev-default 3000 so the
// self-booted `webServer` never collides with a developer's running `next dev`.
const WEB_PORT = Number(new URL(WEB_BASE_URL).port || "3100");
const WEB_DIR = resolve(__dirname, "..", "web");

// The server-free smoke (US-QA-D01, `@smoke`) must keep CI green with NO app up.
// `e2e:smoke` sets E2E_NO_WEBSERVER=1 so Playwright does NOT boot the web app for
// that lane. The browser smoke (US-QA-D18, `@web`) self-boots `next build && start`.
const SKIP_WEBSERVER = !!process.env.E2E_NO_WEBSERVER;

// The LIVE lane (US-E7-01, `@live`) drives the REAL stack (web → api :8000 → db).
// `E2E_LIVE=1` self-boots the web app with `next dev` (NOT `next build` — the
// sandbox blocks the build-time Google-Fonts fetch) on a SEPARATE port (3200, so
// it never collides with the @web build on 3100 or a dev `next dev` on 3000) and
// points it at the live backend via NEXT_PUBLIC_API_BASE_URL. The web BUILD env
// (NEXT_PUBLIC_API_BASE_URL=:8000) is what makes the SSR product resolver + the
// `/api/*` proxy handlers talk to the real FastAPI. Only the @live spec runs in
// this lane (single chromium project — the live DB is shared mutable state, so a
// second viewport racing the same buyer's cart/orders would be self-defeating).
const LIVE = LIVE_LANE;

export default defineConfig({
  testDir: "./tests",
  // Glob keeps spec discovery explicit; smoke + future navigation specs both match.
  testMatch: "**/*.spec.ts",
  // Fail the build if someone leaves a `test.only` in a committed spec.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Single worker by design: the `@web` lane drives Iris's mock route handlers,
  // whose cart/orders/seller stores are PROCESS-GLOBAL in-memory state on the one
  // self-booted server (ADR-0037). Running the two viewport projects in parallel
  // would let them clobber each other's shared cart mid-flight (US-QA-D20). The
  // server-free `@smoke` lane is stateless, so this only constrains `@web`.
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB_BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: LIVE
    ? [
        // The @live lane runs ONE chromium project: the live DB is shared mutable
        // state (the buyer's real cart/orders persist), so racing two viewports
        // over the same money-path would be self-defeating. Desktop is enough to
        // prove the live stack end-to-end.
        { name: "live-chromium", use: { ...devices["Desktop Chrome"] } },
      ]
    : [
        // US-QA-D18 acceptance: the browser smoke must run on desktop AND mobile.
        // Two projects = two real viewport/UA matrices over the same specs.
        {
          name: "desktop-chromium",
          use: { ...devices["Desktop Chrome"] },
        },
        {
          name: "mobile-chromium",
          // Pixel 5 = mobile Chromium (393×851, touch, mobile UA). Keeps the
          // engine chromium-only so a single `playwright install chromium` covers
          // both lanes in the sandbox/CI; the matrix difference is the viewport.
          use: { ...devices["Pixel 5"] },
        },
      ],
  // Self-boot the Next.js app so the suite is key-free / backend-free: it renders
  // static/SSR routes, auth screens, and the shell without a live API (the shell
  // degrades to signed-out when /auth/me is unreachable — exactly this scenario).
  // Skipped for the `@smoke` lane (E2E_NO_WEBSERVER=1) to preserve the Day-1
  // "smoke stays green with no server" invariant (ADR-0012).
  webServer: SKIP_WEBSERVER
    ? undefined
    : LIVE
      ? {
          // LIVE lane: `next dev` (NOT build — sandbox blocks the build-time
          // Google-Fonts fetch), wired to the real backend. NEXT_PUBLIC_API_BASE_URL
          // is what makes the SSR product resolver + `/api/*` proxy hit :8000.
          command: `npm run dev -- --port ${WEB_PORT}`,
          cwd: WEB_DIR,
          url: WEB_BASE_URL,
          timeout: 180_000,
          reuseExistingServer: !process.env.CI,
          stdout: "pipe",
          stderr: "pipe",
          env: {
            NEXT_PUBLIC_API_BASE_URL: API_BASE_URL,
            API_BASE_URL,
          },
        }
      : {
          command: `npm run build && npm run start -- --port ${WEB_PORT}`,
          cwd: WEB_DIR,
          url: WEB_BASE_URL,
          timeout: 180_000,
          reuseExistingServer: !process.env.CI,
          stdout: "pipe",
          stderr: "pipe",
        },
});
