import { NextResponse } from "next/server";
import type {
  Envelope,
  FulfilRequest,
  OrderSummary,
  SellerFulfilItem,
} from "@/lib/api-types";
import { apiFetch } from "@/lib/api";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `PATCH /seller/order-items/{id}/fulfil` (Day-24 flip-to-live, ADR-0040).
 * Mark a line fulfilled / cancelled (partial fulfilment allowed; `pending` is
 * not a valid target → 422). Errors (403/404/422) flow through the canonical
 * envelope so the UI can branch on the `code`.
 *
 * The backend's fulfil PATCH returns the whole `OrderSummary` (NO line
 * snapshots), so we cannot return the FULL updated line. We echo a
 * `SellerFulfilItem` carrying the line `id` + the requested `fulfil_status` (the
 * only field that changed); the snapshot fields are left blank. `FulfilRow`
 * reconciles by taking ONLY `fulfil_status` off this echo and keeping its own
 * snapshot, so the blanks never reach the UI. The fulfil table's row source is
 * now live via `GET /seller/orders/{id}` (see `@/lib/adapters/seller`).
 */
export const dynamic = "force-dynamic";

export async function PATCH(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  const parsed = await readJson<FulfilRequest>(request);
  if ("response" in parsed) return parsed.response;

  try {
    const summaryEnv = await apiFetch<OrderSummary>(
      `/seller/order-items/${id}/fulfil`,
      { method: "PATCH", body: parsed.body, token: auth.token },
    );
    // The live backend returns only the OrderSummary; reflect the change on the
    // line the UI reconciles against (id + new status; snapshots unavailable).
    const item: SellerFulfilItem = {
      id,
      order_number: summaryEnv.data.order_number,
      title_snapshot: "",
      options_snapshot: {},
      qty: 0,
      unit_price_minor: 0,
      currency: summaryEnv.data.currency,
      fulfil_status: parsed.body.fulfil_status,
    };
    const envelope: Envelope<SellerFulfilItem> = { data: item, meta: null };
    return NextResponse.json(envelope);
  } catch (err) {
    return toErrorResponse(err, "Could not update fulfilment.");
  }
}
