import { NextResponse } from "next/server";
import type {
  CheckoutRequest,
  Envelope,
  OrderDetail,
  OrderSummary,
  PageMeta,
} from "@/lib/api-types";
import { checkout, listOrders } from "@/lib/mock/orders";

/**
 * MOCK `POST /orders` (checkout: open cart → order, idempotent) + `GET /orders`
 * (my orders list). Mutates/reads the shared mock orders store (ADR-0037). At
 * the W3 gate these proxy the contract `/orders` with the session token + the
 * `Idempotency-Key` header passed through server-side.
 */

export async function POST(request: Request): Promise<NextResponse> {
  let body: CheckoutRequest;
  try {
    body = (await request.json()) as CheckoutRequest;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  // Idempotency-Key header is preferred; the body field is the documented fallback.
  const key =
    request.headers.get("Idempotency-Key") ?? body.idempotency_key ?? null;

  const result = checkout(body.ship_address, key);
  if ("error" in result) {
    return NextResponse.json(
      { error: { code: "empty_cart", message: "Your cart is empty.", details: null } },
      { status: 409 },
    );
  }

  const envelope: Envelope<OrderDetail> = { data: result.order, meta: null };
  // Replays return 200 with the original order; first creation returns 201.
  return NextResponse.json(envelope, { status: result.replayed ? 200 : 201 });
}

export function GET(): NextResponse {
  const orders = listOrders();
  const meta: PageMeta = {
    next_cursor: null,
    limit: orders.length,
    total: orders.length,
  };
  const envelope: Envelope<OrderSummary[]> = { data: orders, meta };
  return NextResponse.json(envelope);
}
