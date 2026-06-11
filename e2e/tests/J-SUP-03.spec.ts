import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-SUP-03 — Escalate to human (HITL) + audit log. Agent-involved (RAGAS).
// EDGE / HITL: every agent action is logged and traceable.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-SUP-03: Escalate to human (HITL) + audit log", () => {
  test.fixme("support escalates to a human and the flow parks", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/support`);
    await page.getByTestId(TID.support.escalateHitl).click();
    // After escalation, an audit-log entry records the action.
    await expect(page.getByTestId(TID.support.auditLogEntry).first()).toBeVisible();
  });

  test.fixme("every agent action is logged and traceable", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/support`);
    await page.getByTestId(TID.agent.chatInput).fill("look up ORDER-KNOWN-001 and propose a fix");
    await page.getByTestId(TID.agent.chatSend).click();
    // Each agent action leaves an auditable entry.
    await expect(page.getByTestId(TID.support.auditLogEntry).first()).toBeVisible();
  });
});
