// Visible, headed end-to-end audit driver. Opens a real Chromium window on
// DISPLAY=:0 so the human can watch, walks the core journeys, screenshots each
// state to /tmp/hearth-audit/, and records console + network failures.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.AUDIT_BASE ?? "http://localhost:3000";
const OUT = "/tmp/hearth-audit";
mkdirSync(OUT, { recursive: true });

const findings = [];
const note = (m) => { console.log("•", m); findings.push(m); };

const browser = await chromium.launch({ headless: false, slowMo: 650 });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

const consoleErrors = [];
const netFails = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
page.on("requestfailed", (r) => netFails.push(`${r.method()} ${r.url()} — ${r.failure()?.errorText}`));
page.on("response", (r) => { if (r.status() >= 500) netFails.push(`${r.status()} ${r.url()}`); });

const shot = async (name) => {
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`   📸 ${name}.png`);
};

async function go(path, name, waitFor) {
  try {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 20000 });
    if (waitFor) await page.waitForSelector(waitFor, { timeout: 8000 }).catch(() => note(`[${name}] missing selector ${waitFor}`));
    await shot(name);
  } catch (e) { note(`[${name}] navigation error: ${String(e).slice(0, 160)}`); }
}

// 1) Logged-out core pages
await go("/", "01-home");
await go("/search", "02-search-loggedout");
await go("/login", "03-login");

// 2) Log in as the seeded buyer (through the UI, not the API)
try {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[type="email"], input[name="email"]', "ada@buyers.hearth.test");
  await page.fill('input[type="password"], input[name="password"]', "CHANGE_ME_test_pw");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`[login] after submit, url = ${page.url()}`);
  await shot("04-after-login");
} catch (e) { note(`[login] flow error: ${String(e).slice(0, 160)}`); }

// 3) Search + a product detail page
await go("/search", "05-search-loggedin");
try {
  const card = page.locator('a[href^="/product/"]').first();
  if (await card.count()) { await card.click(); await page.waitForTimeout(2000); await shot("06-pdp"); }
  else note("[search] no product cards rendered (thin/empty catalog?)");
} catch (e) { note(`[pdp] ${String(e).slice(0, 160)}`); }

// 4) Agent chat — type a real shopping turn and watch it stream
try {
  await page.goto(`${BASE}/search`, { waitUntil: "domcontentloaded" });
  const input = page.locator('[data-testid="agent-chat-input"], textarea, input[type="text"]').first();
  if (await input.count()) {
    await input.fill("I need a gift for someone who loves pour-over coffee, under $80");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(6000); // let it stream / clarify / error
    await shot("07-agent-reply");
    note(`[agent] body now contains 'error'? ${(await page.content()).toLowerCase().includes("error")}`);
  } else note("[agent] no chat input found on /search");
} catch (e) { note(`[agent] ${String(e).slice(0, 160)}`); }

// 5) Cart + checkout
await go("/cart", "08-cart");
await go("/checkout", "09-checkout");
await go("/orders", "10-orders");

// 6) Seller dashboard — log in as the seeded seller
try {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[type="email"], input[name="email"]', "mara@makers.hearth.test");
  await page.fill('input[type="password"], input[name="password"]', "CHANGE_ME_test_pw");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
} catch (e) { note(`[seller-login] ${String(e).slice(0, 160)}`); }
await go("/seller", "11-seller");

// favicon / metadata
const favResp = await page.goto(`${BASE}/favicon.ico`).catch(() => null);
note(`[favicon] /favicon.ico -> ${favResp ? favResp.status() : "no response"}`);

writeFileSync(`${OUT}/findings.json`, JSON.stringify({ findings, consoleErrors, netFails }, null, 2));
console.log("\n===== CONSOLE ERRORS =====");
console.log(consoleErrors.length ? [...new Set(consoleErrors)].join("\n") : "(none)");
console.log("\n===== NETWORK FAILURES (failed / 5xx) =====");
console.log(netFails.length ? [...new Set(netFails)].join("\n") : "(none)");
console.log("\n===== NOTES =====");
console.log(findings.join("\n"));

await page.waitForTimeout(2500);
await browser.close();
