// -----------------------------------------------------------------------------
// Canonical fixture manifest — the BROWSER layer's view of the 'one source'.
//
// US-QA-D06. This is a typed import of the SAME definition the API + agent layers
// use: api/tests/fixtures/fixture-manifest.json, generated from the Python handles
// in api/tests/fixtures/handles.py. Do NOT hand-edit the JSON — regenerate with:
//
//     (cd api && python -m tests.fixtures.manifest)
//
// The Python spine test (test_fixture_spine.py) asserts the on-disk JSON matches
// the live handles, so this file can never silently drift from the seed.
//
// Use in a J-* spec to seed URLs / pick a persona to log in / assert a known price:
//   import { FIXTURES } from "./_fixtures";
//   await page.goto(`${WEB_BASE_URL}/products/${FIXTURES.products.mug.slug}`);
//   // log in FIXTURES.personas.buyer_primary via the API, reuse storageState, etc.
// -----------------------------------------------------------------------------

import manifest from "../../api/tests/fixtures/fixture-manifest.json";

export interface PersonaFixture {
  email: string;
  display_name: string;
  role: "buyer" | "seller" | "support" | "admin";
  password: string;
}
export interface ProductFixture {
  slug: string;
  title: string;
  store_slug: string;
}
export interface VariantFixture {
  sku: string;
  product_slug: string;
  price_minor: number;
  qty_on_hand: number;
  restock_eta_days: number | null;
  in_stock: boolean;
}
export interface PolicyFixture {
  key: string;
  kind: string;
  store_slug: string | null;
  title: string;
}
export interface PaymentTestMode {
  capture_outcome: string;
  decline_outcome: string;
  declined_error_code: string;
  declined_http_status: number;
}

export interface FixtureManifest {
  personas: Record<string, PersonaFixture>;
  products: Record<string, ProductFixture>;
  variants: Record<string, VariantFixture>;
  policies: Record<string, PolicyFixture>;
  return_reasons: string[];
  payment_test_mode: PaymentTestMode;
}

export const FIXTURES = manifest as unknown as FixtureManifest;
