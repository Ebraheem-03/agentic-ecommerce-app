import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SEL-01 — Onboard seller account. Not agent-involved.
// Edge: incomplete profile blocks publish.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SEL-01: Onboard seller account", () => {
  test.fixme("seller completes onboarding and reaches the dashboard", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await expect(page.getByTestId(TID.seller.page)).toBeVisible();
    await expect(page.getByTestId(TID.seller.onboarding)).toBeVisible();
  });

  test.fixme("incomplete profile blocks publish", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await expect(page.getByTestId(TID.seller.profileIncomplete)).toBeVisible();
    await expect(page.getByTestId(TID.seller.listSubmit)).toBeDisabled();
  });
});
