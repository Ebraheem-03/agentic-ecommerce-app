import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-BUY-05 — Track order / order status. Partial agent involvement.
// Edge: status lookup for unknown / foreign order id.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-BUY-05: Track order / order status", () => {
  test.fixme("buyer looks up a known order and sees its timeline", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/orders`);
    await expect(page.getByTestId(TID.orderStatus.page)).toBeVisible();
    await page.getByTestId(TID.orderStatus.lookupInput).fill("ORDER-KNOWN-001");
    await page.getByTestId(TID.orderStatus.lookupSubmit).click();
    await expect(page.getByTestId(TID.orderStatus.timeline)).toBeVisible();
    await expect(page.getByTestId(TID.orderStatus.step).first()).toBeVisible();
  });

  test.fixme("unknown / foreign order id -> honest not-found, no fabrication", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/orders`);
    await page.getByTestId(TID.orderStatus.lookupInput).fill("ORDER-DOES-NOT-EXIST");
    await page.getByTestId(TID.orderStatus.lookupSubmit).click();
    await expect(page.getByTestId(TID.orderStatus.notFound)).toBeVisible();
    await expect(page.getByTestId(TID.orderStatus.timeline)).toHaveCount(0);
  });
});
