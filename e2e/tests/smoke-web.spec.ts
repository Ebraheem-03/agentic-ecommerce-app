import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { TID } from "./_selectors";

// -----------------------------------------------------------------------------
// Browser smoke (US-QA-D18, `@web`).
//
// Boots the Next.js foundation (via the `webServer` block in playwright.config.ts:
// `next build && next start` on a pinned port) and proves it is HEALTHY in a real
// browser, on DESKTOP AND MOBILE viewports (the two projects in the config run
// every test here twice). This is intentionally KEY-FREE and BACKEND-FREE: it
// asserts static/SSR render, routing, the auth SCREENS, the app shell, and an
// a11y baseline — NOT real auth round-trips (those are a later integrated E2E
// once the API is up, and stay `test.fixme` in the J-* journey specs).
//
// Why a separate file (not a J-* journey): the J-* specs are server+API journeys
// that remain `test.fixme`; this is the standalone, no-API boot/route/a11y gate.
// Tagged `@web` so the server-free `@smoke` lane (US-QA-D01) stays green with no
// app running, while `npm run e2e:web` exercises the booted app.
// -----------------------------------------------------------------------------

// axe gate: zero SERIOUS or CRITICAL violations. (moderate/minor are tracked but
// not gated at the smoke layer — they get routed to Iris as findings, not fails.)
const GATED_IMPACTS = new Set(["serious", "critical"]);

async function axeSeriousCritical(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations.filter((v) => GATED_IMPACTS.has(v.impact ?? ""));
}

// Compact, debuggable failure message listing each gated violation + a sample node.
function formatViolations(
  violations: Awaited<ReturnType<typeof axeSeriousCritical>>,
): string {
  return violations
    .map(
      (v) =>
        `[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node(s))\n` +
        `    e.g. ${v.nodes[0]?.target?.join(" ")}`,
    )
    .join("\n");
}

test.describe("@web browser smoke — route health", () => {
  test("home route is 200 and renders its page root", async ({ page }) => {
    const res = await page.goto("/");
    expect(res?.status(), "GET / should be 200").toBe(200);
    await expect(page.getByTestId(TID.home.page)).toBeVisible();
    await expect(page).toHaveTitle(/Hearth/i);
  });

  test("login route is 200 and renders its page root", async ({ page }) => {
    const res = await page.goto("/login");
    expect(res?.status(), "GET /login should be 200").toBe(200);
    await expect(page.getByTestId(TID.auth.loginPage)).toBeVisible();
  });

  test("register route is 200 and renders its page root", async ({ page }) => {
    const res = await page.goto("/register");
    expect(res?.status(), "GET /register should be 200").toBe(200);
    await expect(page.getByTestId(TID.auth.registerPage)).toBeVisible();
  });

  // Placeholder shop routes must RESOLVE (no 500). They are signed-out / static
  // shells today — the API isn't up — so a 200 render of the page root is enough.
  for (const [name, path, tid] of [
    ["search", "/search", TID.page.search],
    ["cart", "/cart", TID.page.cart],
    ["checkout", "/checkout", TID.page.checkout],
    ["orders", "/orders", TID.page.orderStatus],
    ["seller", "/seller", TID.page.seller],
  ] as const) {
    test(`placeholder route /${name} resolves without a 500`, async ({ page }) => {
      const res = await page.goto(path);
      const status = res?.status() ?? 0;
      expect(status, `GET ${path} should not 5xx`).toBeLessThan(500);
      expect(status, `GET ${path} should be 200`).toBe(200);
      await expect(page.getByTestId(tid)).toBeVisible();
    });
  }
});

test.describe("@web browser smoke — auth screens", () => {
  test("login screen: form + labelled fields + submit", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByTestId(TID.auth.loginForm)).toBeVisible();

    // Programmatic labelling (a11y A6): getByLabel resolves the input only when
    // the <label htmlFor> ↔ input id association is correct.
    const email = page.getByLabel("Email");
    const password = page.getByLabel("Password");
    await expect(email).toBeVisible();
    await expect(email).toHaveAttribute("type", "email");
    await expect(password).toBeVisible();
    await expect(password).toHaveAttribute("type", "password");
    // The labelled inputs are the same nodes the registry anchors.
    await expect(email).toHaveAttribute("data-testid", TID.auth.loginEmail);
    await expect(password).toHaveAttribute("data-testid", TID.auth.loginPassword);

    await expect(page.getByTestId(TID.auth.loginSubmit)).toBeVisible();

    // Error region is a role="alert" rendered ON DEMAND (correct a11y — an empty
    // live region is an anti-pattern). With no API we can't trigger a server
    // error, but we CAN prove the client-side error path wires up: submitting an
    // empty form runs local validation and surfaces a field-tied error.
    await page.getByTestId(TID.auth.loginSubmit).click();
    const emailError = page.locator("#login-email-error");
    await expect(emailError).toBeVisible();
    await expect(email).toHaveAttribute("aria-describedby", "login-email-error");
    await expect(email).toHaveAttribute("aria-invalid", "true");
  });

  test("register screen: form, labelled fields, role choice, submit", async ({
    page,
  }) => {
    await page.goto("/register");

    await expect(page.getByTestId(TID.auth.registerForm)).toBeVisible();

    const name = page.getByLabel("Name");
    const email = page.getByLabel("Email");
    const password = page.getByLabel("Password");
    await expect(name).toBeVisible();
    await expect(email).toBeVisible();
    await expect(password).toBeVisible();
    await expect(name).toHaveAttribute("data-testid", TID.auth.registerName);

    // Buyer/seller role radios per the RegisterRequest contract.
    await expect(page.getByTestId(TID.auth.registerRoleBuyer)).toBeVisible();
    await expect(page.getByTestId(TID.auth.registerRoleSeller)).toBeVisible();
    // Buyer is the default selection.
    await expect(page.getByTestId(TID.auth.registerRoleBuyer)).toBeChecked();

    await expect(page.getByTestId(TID.auth.registerSubmit)).toBeVisible();

    // Client validation surfaces a field-tied error region on empty submit.
    await page.getByTestId(TID.auth.registerSubmit).click();
    await expect(page.locator("#register-name-error")).toBeVisible();
    await expect(name).toHaveAttribute("aria-describedby", "register-name-error");
  });
});

test.describe("@web browser smoke — app shell", () => {
  // The full shell (skip link, primary nav, footer) is the (shop) layout, which
  // wraps home and the shop routes. Auth pages use a deliberately minimal chrome,
  // so shell landmarks are asserted on `/`.
  test("home renders header, primary nav, skip link, footer", async ({
    page,
  }) => {
    await page.goto("/");

    // Header landmark (one <header> banner).
    await expect(page.getByRole("banner")).toBeVisible();

    // Primary nav anchor from the registry. On mobile it is visually collapsed
    // behind the trigger, so assert presence (attached) rather than visibility to
    // keep the assertion viewport-agnostic across both projects.
    await expect(page.getByTestId(TID.home.nav)).toBeAttached();
    await expect(page.getByTestId(TID.home.cartLink)).toBeVisible();

    // Skip link: present, and the only main landmark it targets exists.
    await expect(
      page.getByRole("link", { name: /skip to content/i }),
    ).toBeAttached();
    await expect(page.locator("main#main")).toBeVisible();

    // Footer landmark.
    await expect(page.getByRole("contentinfo")).toBeVisible();
  });

  test("exactly one h1 on home (landmark/heading order, a11y A5)", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  });
});

test.describe("@web browser smoke — a11y baseline (axe)", () => {
  // Zero serious/critical axe violations on the three key routes, run on BOTH the
  // desktop and mobile projects. If markup regresses, this fails with the exact
  // rule + offending node so it can be routed back to Iris.
  for (const [name, path] of [
    ["home", "/"],
    ["login", "/login"],
    ["register", "/register"],
  ] as const) {
    test(`${name} has no serious/critical a11y violations`, async ({ page }) => {
      await page.goto(path);
      const violations = await axeSeriousCritical(page);
      expect(
        violations,
        violations.length
          ? `axe found ${violations.length} serious/critical violation(s) on ${path}:\n${formatViolations(violations)}`
          : "",
      ).toEqual([]);
    });
  }
});
