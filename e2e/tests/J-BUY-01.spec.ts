import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-BUY-01 — Discover: conversational search over catalog. Agent-involved (RAGAS).
// Edge: out-of-scope / ambiguous query -> graceful clarify, not hallucination.
// Skeleton only (US-QA-D03): no running server. Flip `test.fixme` -> `test` and
// add `webServer` to playwright.config.ts when web + api scaffold is up.

test.describe("J-BUY-01: Discover — conversational search over catalog", () => {
  test.fixme("buyer asks in natural language and gets grounded results", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    // 1. Land on home, open the conversational search surface.
    await expect(page.getByTestId(TID.home.page)).toBeVisible();
    await page.getByTestId(TID.home.searchEntry).click();
    // 2. Type an intent-rich query into the agent chat.
    await page.getByTestId(TID.agent.chatInput).fill("a warm rug for a small living room");
    await page.getByTestId(TID.agent.chatSend).click();
    // 3. Agent responds with grounded recommendation cards.
    await expect(page.getByTestId(TID.agent.recommendationCard).first()).toBeVisible();
    await expect(page.getByTestId(TID.search.resultCard).first()).toBeVisible();
  });

  test.fixme("ambiguous / out-of-scope query -> clarify, not hallucination", async ({ page }) => {
    await page.goto(WEB_BASE_URL);
    await page.getByTestId(TID.agent.chatInput).fill("asdfqwer ???");
    await page.getByTestId(TID.agent.chatSend).click();
    // Edge: agent must ask to clarify instead of inventing results.
    await expect(page.getByTestId(TID.agent.clarifyPrompt)).toBeVisible();
  });
});
