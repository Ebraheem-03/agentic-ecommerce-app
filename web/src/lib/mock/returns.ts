import type { ReturnCreate, ReturnItemOut, ReturnOut } from "@/lib/api-types";
import { getOrder, markReturnRequested } from "@/lib/mock/orders";

/**
 * MOCK returns store (ADR-0037). Backs `POST /orders/{id}/returns` (+ a cheap
 * list) deterministically. The HITL path is modeled off the order's window:
 *  - order within the return window (`return_eligible`) → a `requested` return
 *    (the normal path; a human/support still decides, but it's in-window).
 *  - order OUTSIDE the window → the return lands in `hitl_pending` — the
 *    contract's agent-assisted HITL deferral (`order-status-hitl-pending`),
 *    surfaced so the human-in-the-loop decision is visible in the UI.
 */

let returnSeq = 5000;
const returns: ReturnOut[] = [];

export function createReturn(
  orderId: string,
  body: ReturnCreate,
): ReturnOut | { error: "not_found" } {
  const order = getOrder(orderId);
  if (!order) return { error: "not_found" };

  const withinWindow = order.return_eligible === true;
  const items: ReturnItemOut[] = body.items.map((it, i) => ({
    id: `ri_${++returnSeq}_${i}`,
    order_item_id: it.order_item_id,
    qty: it.qty,
  }));

  const now = new Date().toISOString();
  const ret: ReturnOut = {
    id: `ret_${++returnSeq}`,
    order_id: orderId,
    // Out-of-window → HITL deferral; in-window → standard request.
    status: withinWindow ? "requested" : "hitl_pending",
    reason_code: body.reason_code,
    note: body.note ?? null,
    within_window: withinWindow,
    approved_by: null,
    items,
    created_at: now,
    resolved_at: null,
  };
  returns.push(ret);
  markReturnRequested(orderId);
  return ret;
}

export function listReturns(orderId?: string): ReturnOut[] {
  return returns.filter((r) => !orderId || r.order_id === orderId);
}
