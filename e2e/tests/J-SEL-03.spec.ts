import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SEL-03 — Receive merchandising/pricing nudge. Agent-involved (RAGAS).
// Edge: nudge grounded in real catalog data, not invented.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SEL-03: Receive merchandising/pricing nudge", () => {
  test.fixme("seller sees an actionable nudge after listing", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await expect(page.getByTestId(TID.seller.nudge)).toBeVisible();
  });

  test.fixme("nudge is grounded in real catalog data, not invented", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    // The grounding/reason anchor must cite real catalog context.
    await expect(page.getByTestId(TID.seller.nudgeReason)).toBeVisible();
  });
});
