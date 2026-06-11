import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-ADM-02 — Adjust agent guardrails / policy. Agent-involved (RAGAS).
// EDGE / regression: change observably alters agent behavior (regression-checked).
// Skeleton only (US-QA-D03): no running server.

test.describe("J-ADM-02: Adjust agent guardrails / policy", () => {
  test.fixme("admin edits a guardrail and saves it", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/admin`);
    await expect(page.getByTestId(TID.admin.guardrailEditor)).toBeVisible();
    await page.getByTestId(TID.admin.guardrailSave).click();
  });

  test.fixme("guardrail change observably alters agent behavior", async ({ page }) => {
    // Regression check: after saving a stricter guardrail, the agent now refuses
    // a prompt it previously allowed. Pairs with the agent eval suite (US-QA-D05).
    await page.goto(`${WEB_BASE_URL}/admin`);
    await page.getByTestId(TID.admin.guardrailSave).click();
    await page.goto(`${WEB_BASE_URL}/support`);
    await page.getByTestId(TID.agent.chatInput).fill("a prompt the new guardrail should now block");
    await page.getByTestId(TID.agent.chatSend).click();
    await expect(page.getByTestId(TID.agent.refusalNotice)).toBeVisible();
  });
});
