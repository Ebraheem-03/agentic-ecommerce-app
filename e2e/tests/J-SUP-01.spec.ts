import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SUP-01 — Look up order by id / customer. Partial agent involvement.
// Edge: order not found -> honest "no record", no fabrication.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SUP-01: Look up order by id / customer", () => {
  test.fixme("support finds a known order", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/support`);
    await expect(page.getByTestId(TID.support.console)).toBeVisible();
    await page.getByTestId(TID.orderStatus.lookupInput).fill("ORDER-KNOWN-001");
    await page.getByTestId(TID.orderStatus.lookupSubmit).click();
    await expect(page.getByTestId(TID.orderStatus.summary)).toBeVisible();
  });

  test.fixme("order not found -> honest no-record, no fabrication", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/support`);
    await page.getByTestId(TID.orderStatus.lookupInput).fill("ORDER-DOES-NOT-EXIST");
    await page.getByTestId(TID.orderStatus.lookupSubmit).click();
    await expect(page.getByTestId(TID.orderStatus.notFound)).toBeVisible();
  });
});
