import { test, expect } from "@playwright/test";
import { WEB_BASE_URL } from "../playwright.config";
import { TID } from "./_selectors";

// J-ADM-01 — Review catalog / policies. Not agent-involved.
// Skeleton only (US-QA-D03): no running server.

test.describe("J-ADM-01: Review catalog / policies", () => {
  test.fixme("admin reviews the catalog / policy table", async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}/admin`);
    await expect(page.getByTestId(TID.admin.console)).toBeVisible();
    await expect(page.getByTestId(TID.admin.policyTable)).toBeVisible();
  });
});
