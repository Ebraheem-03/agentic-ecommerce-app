import { NextResponse } from "next/server";
import type { Envelope, ReturnCreate, ReturnOut } from "@/lib/api-types";
import { createReturn, listReturns } from "@/lib/mock/returns";

/**
 * MOCK `POST /orders/{id}/returns` → `ReturnOut` (201) + a cheap `GET` list.
 * Models the HITL path (ADR-0037): a return on an in-window order is `requested`;
 * an out-of-window order's return lands in `hitl_pending` (the contract's
 * agent-assisted HITL deferral, `order-status-hitl-pending`). At the W3 gate
 * this proxies the contract `/orders/{id}/returns`.
 */

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  let body: ReturnCreate;
  try {
    body = (await request.json()) as ReturnCreate;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }
  if (!Array.isArray(body.items) || body.items.length === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Choose at least one item to return.", details: null } },
      { status: 422 },
    );
  }

  const result = createReturn(id, body);
  if ("error" in result) {
    return NextResponse.json(
      { error: { code: "not_found", message: "We couldn't find that order.", details: null } },
      { status: 404 },
    );
  }
  const envelope: Envelope<ReturnOut> = { data: result, meta: null };
  return NextResponse.json(envelope, { status: 201 });
}

export async function GET(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  const data = listReturns(id);
  const envelope: Envelope<ReturnOut[]> = {
    data,
    meta: { next_cursor: null, limit: data.length, total: data.length },
  };
  return NextResponse.json(envelope);
}
