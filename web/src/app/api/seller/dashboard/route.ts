import { NextResponse } from "next/server";
import type { Envelope, SellerDashboard } from "@/lib/api-types";
import { getDashboard } from "@/lib/mock/seller";

// MOCK until the returns/seller backend lands (Day-22 scope call; ADR-0040).
/**
 * MOCK `GET /seller/dashboard` → the maker dashboard aggregate (a display-only
 * convenience that fans out to the contract's `GET /seller/orders` +
 * `/seller/nudges` + the listings/inventory snapshot). Reads the shared mock
 * seller store (ADR-0037). At the W3 gate the page composes the real
 * `/seller/*` endpoints; this single read is the local stand-in.
 */
export function GET(): NextResponse {
  const envelope: Envelope<SellerDashboard> = { data: getDashboard(), meta: null };
  return NextResponse.json(envelope);
}
