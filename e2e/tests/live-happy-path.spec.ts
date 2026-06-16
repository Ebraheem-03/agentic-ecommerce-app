import { test, expect, type Page } from "@playwright/test";
import { TID } from "./_selectors";
import { API_BASE_URL } from "../playwright.config";

// -----------------------------------------------------------------------------
// LIVE deterministic happy path (US-E7-01, `@live`).
//
// Drives the WHOLE buyer money-path against the REAL stack — web (next dev, the
// `/api/*` proxy handlers + SSR product resolver) → FastAPI :8000 → Postgres —
// with ZERO mocks:
//
//   log in as ada (real session cookie)
//     → reach a PDP the DETERMINISTIC way (direct seeded slug, NOT Ember chat)
//     → add to cart  → /cart shows the real line
//     → checkout → approval gate restates totals → Approve
//     → two-step payment (intent → confirm, captured)
//     → order confirmation  → /orders shows the placed+paid order + timeline
//
// WHY NON-CONVERSATIONAL ENTRY (critical): DEFECT-D22-01 — the live Ember
// shopping planner LOOPS (re-issues the same `search` every step, never replies),
// so the conversation-first `/search` page cannot complete a turn under the live
// LLM. We therefore NEVER touch Ember chat; we deep-link the PDP by seeded slug.
// The checkout approval gate is FE-orchestrated (ADR-0038) and calls the order
// endpoints DIRECTLY (not the agent runtime), so it works fine live.
//
// LIVE STATE IS NOT PROCESS-GLOBAL MOCKS: the buyer's cart + orders persist in
// the real DB across runs. This spec is robust to pre-existing state — it CLEARS
// the cart at the start (removing whatever lines are there), asserts on the line
// IT adds, and never asserts the orders-LIST length (append-only/shared) — it
// deep-links the freshly placed order by its real id.
//
// DEFECT-D22-02 (NEW, filed to Atlas → Iris): the live `AddressIn` requires
// `region` (min_length 1), but the CheckoutFlow form has NO region field and
// defaults `region: ""`, and `toBackendAddress` passes it through verbatim — so a
// pure-UI checkout 422s on `region`. Per the "patch the TEST, not app code" rule
// (same posture as the D20 HITL data-spine gap), this spec intercepts the
// outbound `POST /api/orders` body and fills a region so the live order still
// PLACES end-to-end (the request still hits :8000 and persists a real row). No
// app code is touched. The defect is reported separately for Iris to fix forward.
// -----------------------------------------------------------------------------

const BUYER_EMAIL = "ada@buyers.hearth.test";
const BUYER_PASSWORD = "CHANGE_ME_test_pw";

// A seeded, in-stock product the PDP resolves live (GET /products/{slug}). Its
// "Natural Tan" variant is in stock; "Espresso" is out of stock.
const SEEDED_SLUG = "carryall-card-wallet";
const SEEDED_TITLE = /Carryall Card Wallet/i;

/**
 * Sign in through the real login form → sets the httpOnly session cookie.
 *
 * HYDRATION NOTE (`next dev`): the page compiles + hydrates on first hit, and the
 * `<form>`'s React `onSubmit` (which `preventDefault`s and POSTs `/api/auth/login`)
 * only attaches after hydration. If we click too early the form submits NATIVELY
 * as a GET (`/login?email=…`) and no cookie is set. So we wait for the submit POST
 * to actually fire before trusting the navigation, and confirm the session by
 * round-tripping `/api/cart` (which 401s when unauthenticated).
 */
async function logInAsAda(page: Page): Promise<void> {
  // Retry the whole load→fill→submit: if a too-early click submits the form
  // NATIVELY (a GET to `/login?email=…`, which clears the inputs), we reload and
  // try again once the page has hydrated. Each attempt waits for hydration before
  // clicking and requires the JS handler's POST to /api/auth/login to fire.
  await expect(async () => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId(TID.auth.loginPage)).toBeVisible();

    // Wait for React to hydrate the client island before interacting. Next 14
    // marks hydration by removing the streaming boundary; a stable proxy is that
    // the document is interactive AND the form has been client-rendered. We give
    // the dev-server a beat to attach the onSubmit handler.
    await page.waitForLoadState("load");
    await page.waitForTimeout(1_500);

    await page.getByTestId(TID.auth.loginEmail).fill(BUYER_EMAIL);
    await page.getByTestId(TID.auth.loginPassword).fill(BUYER_PASSWORD);

    const loginPost = page
      .waitForRequest(
        (req) =>
          req.url().includes("/api/auth/login") && req.method() === "POST",
        { timeout: 5_000 },
      )
      .catch(() => null);
    await page.getByTestId(TID.auth.loginSubmit).click();
    const req = await loginPost;
    expect(
      req,
      "the login form must POST /api/auth/login (hydrated, not a native GET)",
    ).not.toBeNull();
  }).toPass({ timeout: 60_000 });

  // The form navigates home + refreshes server components on success.
  await page.waitForURL("**/", { waitUntil: "domcontentloaded" });

  // Confirm the session cookie really took: an authenticated proxy call succeeds.
  await expect(async () => {
    const res = await page.request.get("/api/cart");
    expect(res.ok(), "signed-in /api/cart should be 200").toBeTruthy();
  }).toPass({ timeout: 15_000 });
}

/**
 * Make the live cart empty so the spec starts from a known state. The buyer's
 * cart persists in the real DB across runs; we read it via the same-origin proxy
 * (the session cookie is attached) and DELETE every existing line.
 */
async function clearLiveCart(page: Page): Promise<void> {
  const res = await page.request.get("/api/cart");
  expect(res.ok(), "GET /api/cart should succeed for the signed-in buyer").toBeTruthy();
  const body = (await res.json()) as { data: { items: { id: string }[] } };
  for (const line of body.data.items) {
    const del = await page.request.delete(`/api/cart/items/${line.id}`);
    expect(del.ok(), `DELETE cart line ${line.id}`).toBeTruthy();
  }
  // Confirm empty.
  const after = (await (await page.request.get("/api/cart")).json()) as {
    data: { items: unknown[] };
  };
  expect(after.data.items).toHaveLength(0);
}

test.describe("@live live deterministic happy path (real web → api :8000 → db)", () => {
  // The whole money-path is ONE ordered flow: clearing/adding/placing all mutate
  // the same live cart, so splitting them would fight over shared DB state.
  test("log in → PDP → cart → checkout gate → pay → order confirmed → /orders", async ({
    page,
  }) => {
    // Sanity: the live backend is actually up before we drive the UI.
    const health = await page.request.get(`${API_BASE_URL}/health`);
    expect(health.ok(), `${API_BASE_URL}/health must be ok`).toBeTruthy();

    // --- LOG IN (real session) --------------------------------------------
    await logInAsAda(page);

    // --- CLEAR pre-existing cart (live state is not a clean slate) ---------
    await clearLiveCart(page);

    // --- PDP the deterministic way (direct seeded slug, NO Ember chat) -----
    await page.goto(`/product/${SEEDED_SLUG}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId(TID.product.page)).toBeVisible();
    await expect(page.getByTestId(TID.product.title)).toHaveText(SEEDED_TITLE);

    // --- ADD TO CART (real POST /cart/items → live cart) ------------------
    // The buy box is a client island; under `next dev` the add-to-cart onClick
    // only fires once hydrated. Retry the click until the (optimistic, then
    // server-confirmed) add registers — confirmed by the real cart having a line.
    await page.waitForTimeout(1_000); // let the freshly-compiled PDP hydrate
    await expect(async () => {
      await page.getByTestId(TID.product.addToCart).click();
      const res = await page.request.get("/api/cart");
      const body = (await res.json()) as { data: { items: unknown[] } };
      expect(body.data.items.length, "the live cart has the added line").toBeGreaterThan(0);
    }).toPass({ timeout: 20_000 });

    // --- /cart shows the REAL line ----------------------------------------
    await page.goto("/cart", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId(TID.cart.page)).toBeVisible();
    const lines = page.getByTestId(TID.cart.lineItem);
    await expect(lines).toHaveCount(1);
    await expect(page.getByTestId(TID.cart.lineTitle)).toHaveText(SEEDED_TITLE);
    // The subtotal is whatever the live catalog prices the variant at (we don't
    // hardcode cents — anti-drift); it must be a real currency amount.
    await expect(page.getByTestId(TID.cart.subtotal)).toHaveText(/\$\d/);

    // --- CHECKOUT: open the approval gate ---------------------------------
    await page.getByTestId(TID.cart.checkoutCta).click();
    await expect(page).toHaveURL(/\/checkout/);
    await expect(page.getByTestId(TID.checkout.page)).toBeVisible();
    await expect(page.getByTestId(TID.checkout.orderSummary)).toBeVisible();

    // DEFECT-D22-02 workaround (test-only, no app code touched): the live
    // AddressIn requires a non-empty `region`, but the checkout form has no
    // region field and defaults "". Fill it on the outbound POST so the live
    // order PLACES — the request still hits the real :8000 → DB.
    await page.route("**/api/orders", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      const raw = route.request().postData() ?? "{}";
      const body = JSON.parse(raw) as {
        ship_address?: { region?: string };
      };
      if (body.ship_address && !body.ship_address.region) {
        body.ship_address.region = "Avon";
      }
      await route.continue({ postData: JSON.stringify(body) });
    });

    // Watch that the order POST does NOT fire before Approve (the gate is real).
    let orderPosted = false;
    page.on("request", (req) => {
      if (req.url().includes("/api/orders") && req.method() === "POST") {
        orderPosted = true;
      }
    });

    await page.getByRole("button", { name: /review with ember/i }).click();
    const gate = page.getByRole("group", { name: /approve checkout/i });
    await expect(gate).toBeVisible();
    // The gate restates EXACTLY what Ember is about to do — BEFORE any charge.
    await expect(gate).toContainText(/Items/);
    await expect(gate).toContainText(/Ship to/);
    await expect(gate).toContainText(/Payment/);
    await expect(gate).toContainText(/Total to charge/);
    await expect(gate).toContainText(/\$/);
    await expect(gate).toContainText(/Nothing is charged until you do/i);
    expect(orderPosted, "no order POST may fire before Approve").toBe(false);
    await expect(page.getByTestId(TID.checkout.confirmation)).toHaveCount(0);

    // --- APPROVE → the gated two-step payment runs LIVE -------------------
    await page.getByTestId(TID.checkout.placeOrder).click();
    await expect(page.getByTestId(TID.checkout.confirmation)).toBeVisible({
      timeout: 30_000,
    });
    expect(orderPosted, "Approve triggers the live order POST").toBe(true);
    const confirmation = page.getByTestId(TID.checkout.confirmation);
    await expect(confirmation).toContainText(/Order placed/i);
    // Capture the real order number that persisted (evidence for the report).
    const confirmText = (await confirmation.textContent()) ?? "";
    const orderNumber = confirmText.match(/HEA-\d{8}-[0-9A-F]+/)?.[0] ?? "";
    expect(orderNumber, "a real HEA-… order number is shown").not.toBe("");
    // Surface it in the run log so Atlas can cross-check the DB row.
    // eslint-disable-next-line no-console
    console.log(`[live-happy-path] placed live order: ${orderNumber}`);
    test.info().annotations.push({
      type: "live-order-number",
      description: orderNumber,
    });

    // --- TRACK → the placed+paid order with its timeline ------------------
    await page.getByRole("link", { name: /track your order/i }).click();
    await expect(page).toHaveURL(/\/orders\?id=/);
    await expect(page.getByTestId(TID.orderStatus.timeline)).toBeVisible();
    const steps = page.getByTestId(TID.orderStatus.step);
    await expect(steps).toHaveCount(4); // placed → packed → shipped → delivered
    // Payment captured → the "Paid" badge, and the per-item snapshot from the DB.
    await expect(page.getByText("Paid", { exact: true })).toBeVisible();
    await expect(page.getByText(SEEDED_TITLE).first()).toBeVisible();
    // The order number shown on the detail matches the one we just placed.
    await expect(page.getByText(orderNumber).first()).toBeVisible();
  });
});
