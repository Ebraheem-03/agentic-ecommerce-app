import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SEL-02 — List a product (create SKU). Not agent-involved.
// Edge: validation errors are clear + labelled (a11y A6).
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SEL-02: List a product (create SKU)", () => {
  test.fixme("seller lists a valid SKU", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await expect(page.getByTestId(TID.seller.listForm)).toBeVisible();
    await page.getByTestId(TID.seller.listSubmit).click();
    // A successful list surfaces the new SKU in the orders/catalog view.
    await expect(page.getByTestId(TID.seller.orders)).toBeVisible();
  });

  test.fixme("invalid listing shows clear, labelled validation errors", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/seller`);
    await page.getByTestId(TID.seller.listSubmit).click();
    await expect(page.getByTestId(TID.seller.listError)).toBeVisible();
  });
});
