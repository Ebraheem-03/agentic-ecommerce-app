import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-BUY-03 — Add to cart from a recommendation. Agent-involved (RAGAS).
// Edge: item went out-of-stock between recommend and add.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-BUY-03: Add to cart from a recommendation", () => {
  test.fixme("buyer adds the agent's recommended item to cart", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    await page.getByTestId(TID.agent.recommendationCard).first().click();
    // 1. Land on product detail for the recommended item.
    await expect(page.getByTestId(TID.product.page)).toBeVisible();
    // 2. Add to cart and confirm.
    await page.getByTestId(TID.product.addToCart).click();
    await expect(page.getByTestId(TID.product.addConfirmation)).toBeVisible();
    await expect(page.getByTestId(TID.home.cartLink)).toContainText(/1/);
  });

  test.fixme("item out-of-stock between recommend and add is handled", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    await page.getByTestId(TID.agent.recommendationCard).first().click();
    // Edge: OOS notice shown; add-to-cart is unavailable, no silent failure.
    await expect(page.getByTestId(TID.product.outOfStock)).toBeVisible();
    await expect(page.getByTestId(TID.product.addToCart)).toBeDisabled();
  });
});
