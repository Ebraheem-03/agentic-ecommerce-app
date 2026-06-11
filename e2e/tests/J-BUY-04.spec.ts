import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-BUY-04 — Checkout (happy path). Not agent-involved.
// Edge: payment decline / address validation.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-BUY-04: Checkout (happy path)", () => {
  test.fixme("buyer completes checkout from a populated cart", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/cart`);
    // 1. Cart has items, proceed to checkout.
    await expect(page.getByTestId(TID.cart.lineItem).first()).toBeVisible();
    await page.getByTestId(TID.cart.checkoutCta).click();
    // 2. Fill address + payment.
    await expect(page.getByTestId(TID.checkout.page)).toBeVisible();
    await page.getByTestId(TID.checkout.addressLine1).fill("1 Hearth Lane");
    // 3. Place order, reach confirmation with an order id.
    await page.getByTestId(TID.checkout.placeOrder).click();
    await expect(page.getByTestId(TID.checkout.confirmation)).toBeVisible();
  });

  test.fixme("address validation error is announced + tied to field", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/checkout`);
    await page.getByTestId(TID.checkout.placeOrder).click();
    await expect(page.getByTestId(TID.checkout.addressError)).toBeVisible();
  });

  test.fixme("payment decline is surfaced, not swallowed", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/checkout`);
    await page.getByTestId(TID.checkout.placeOrder).click();
    await expect(page.getByTestId(TID.checkout.paymentError)).toBeVisible();
  });
});
