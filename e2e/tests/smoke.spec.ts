import { test, expect } from "@playwright/test";
import { WEB_BASE_URL, API_BASE_URL } from "../playwright.config";

// -----------------------------------------------------------------------------
// Day-1 smoke (US-QA-D01).
//
// These pass WITHOUT a running web/api server: a trivial sanity assertion plus a
// guard that the E2E env contract is resolvable. They prove the harness wiring
// (config, env resolution, test discovery, CI slot) end to end before any app
// code exists. Real navigation specs arrive in US-QA-D03 (see fixme stubs below).
// -----------------------------------------------------------------------------

test.describe("@smoke harness foundation", () => {
  test("harness is wired and runnable", () => {
    // Trivial assertion: if Playwright can discover + execute this, the toolchain
    // (config, ts transform, runner) is healthy.
    expect(1 + 1).toBe(2);
  });

  test("env contract resolves to valid base URLs", () => {
    // Guard the env contract documented in e2e/.env.example. Must be set (from
    // real env, e2e/.env, or the example fallback) and be a well-formed URL.
    for (const [name, value] of [
      ["WEB_BASE_URL", WEB_BASE_URL],
      ["API_BASE_URL", API_BASE_URL],
    ] as const) {
      expect(value, `${name} must be set`).toBeTruthy();
      expect(
        () => new URL(value),
        `${name} must be a valid URL, got: ${value}`,
      ).not.toThrow();
    }
  });
});

// -----------------------------------------------------------------------------
// Placeholders for US-QA-D03 — require a live server, so skipped today.
// Flip `test.fixme` -> `test` and add `webServer` to playwright.config.ts when
// the web + api scaffold is up.
// -----------------------------------------------------------------------------
test.describe("real navigation (US-QA-D03)", () => {
  test.fixme("web app serves the landing page", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    await expect(page).toHaveTitle(/.+/);
  });

  test.fixme("api health endpoint is green", async ({ request }) => {
    const res = await request.get(`${API_BASE_URL}/health`);
    expect(res.ok()).toBeTruthy();
  });
});
