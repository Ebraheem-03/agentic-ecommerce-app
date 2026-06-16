/**
 * Order contract → view-model adapters (Day-22 flip-to-live, ADR-0040).
 *
 * `OrderDetail` / `OrderItemOut` / `PaymentOut` already speak `*_minor` on the
 * wire, so they pass through untouched. The ONE mismatch the flip surfaced is
 * the shipping address: the FE form models it as `{ name, country }` but the
 * live `AddressIn` requires `{ recipient_name, country_code }`. We translate in
 * the orders proxy so the checkout component stays unchanged.
 */
import type { AddressIn } from "@/lib/api-types";

/** Backend `AddressIn` — `recipient_name` + a 2-char `country_code`. */
export interface BackendAddressIn {
  recipient_name: string;
  line1: string;
  line2?: string | null;
  city: string;
  region: string;
  postal_code: string;
  country_code: string;
}

/** FE `AddressIn` (`name`/`country`) → backend `AddressIn`. */
export function toBackendAddress(addr: AddressIn): BackendAddressIn {
  return {
    recipient_name: addr.name,
    line1: addr.line1,
    line2: addr.line2 ?? null,
    city: addr.city,
    region: addr.region,
    postal_code: addr.postal_code,
    // FE already collects a 2-letter code (e.g. "US", "GB").
    country_code: addr.country,
  };
}
