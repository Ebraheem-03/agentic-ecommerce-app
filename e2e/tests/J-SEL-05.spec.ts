import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SEL-05 — Fulfil an order. Not agent-involved.
// Edge: partial / cancelled fulfilment.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SEL-05: Fulfil an order", () => {
  test.fixme("seller fulfils an order from the dashboard", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await expect(page.getByTestId(TID.seller.orders)).toBeVisible();
    await page.getByTestId(TID.seller.fulfil).first().click();
  });

  test.fixme("partial / cancelled fulfilment is handled", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await page.getByTestId(TID.seller.fulfil).first().click();
    // Partial/cancel paths keep the order row in a consistent, visible state.
    await expect(page.getByTestId(TID.seller.orders)).toBeVisible();
  });
});
