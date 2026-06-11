import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-BUY-06 — Return + HITL approval. Agent-involved (RAGAS). EDGE / HITL path.
// Edge: outside return window -> agent defers to human (HITL).
// Skeleton only (US-QA-D03): no running server.

test.describe("J-BUY-06: Return + HITL approval", () => {
  test.fixme("buyer starts a return within window and it is accepted", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/orders`);
    await page.getByTestId(TID.orderStatus.lookupInput).fill("ORDER-RETURNABLE-001");
    await page.getByTestId(TID.orderStatus.lookupSubmit).click();
    await page.getByTestId(TID.orderStatus.returnCta).click();
    await expect(page.getByTestId(TID.orderStatus.returnPanel)).toBeVisible();
  });

  test.fixme("outside return window -> agent defers to human (HITL)", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/orders`);
    await page.getByTestId(TID.orderStatus.lookupInput).fill("ORDER-OUT-OF-WINDOW-001");
    await page.getByTestId(TID.orderStatus.lookupSubmit).click();
    await page.getByTestId(TID.orderStatus.returnCta).click();
    // HITL: agent does not auto-approve; flow parks in awaiting-human state.
    await expect(page.getByTestId(TID.orderStatus.hitlPending)).toBeVisible();
  });
});
