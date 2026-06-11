import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-BUY-02 — Compare: agent contrasts candidates with reasons. Agent-involved (RAGAS).
// Edge: conflicting attributes / missing data surfaced honestly.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-BUY-02: Compare — agent contrasts candidates with reasons", () => {
  test.fixme("agent surfaces a defensible best-value pick with a clear why", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    await page.getByTestId(TID.agent.chatInput).fill("compare the two cheapest wool rugs");
    await page.getByTestId(TID.agent.chatSend).click();
    // Multiple candidate cards, each carrying a reason.
    await expect(page.getByTestId(TID.agent.recommendationCard).first()).toBeVisible();
    await expect(page.getByTestId(TID.agent.recommendationReason).first()).toBeVisible();
  });

  test.fixme("conflicting / missing attributes are surfaced honestly", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    await page.getByTestId(TID.agent.chatInput).fill("which is more durable?");
    await page.getByTestId(TID.agent.chatSend).click();
    // Edge: where data is missing, the reason text states it rather than inventing.
    await expect(page.getByTestId(TID.agent.recommendationReason).first()).toBeVisible();
  });
});
