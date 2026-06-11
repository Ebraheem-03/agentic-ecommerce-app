import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SEL-04 — Publish merchandising change (accept nudge). Agent-involved (RAGAS).
// EDGE / merch-publish path: publish is reversible / audited.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SEL-04: Publish merchandising change (accept nudge)", () => {
  test.fixme("seller accepts the nudge in one step and it publishes", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await expect(page.getByTestId(TID.seller.nudge)).toBeVisible();
    await page.getByTestId(TID.seller.nudgeAccept).click();
    // Publish leaves an audit trace and is reversible.
    await expect(page.getByTestId(TID.seller.publishAudit)).toBeVisible();
  });

  test.fixme("publish is reversible / audited", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await page.getByTestId(TID.seller.nudgeAccept).click();
    // Audit notice records the change so it can be reverted.
    await expect(page.getByTestId(TID.seller.publishAudit)).toBeVisible();
  });
});
