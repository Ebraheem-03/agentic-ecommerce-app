import { NextResponse } from "next/server";
import type { Envelope, ReturnCreate, ReturnOut } from "@/lib/api-types";
import { apiFetch } from "@/lib/api";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE returns proxy (Day-24 flip-to-live, ADR-0040):
 *  - `POST /orders/{id}/returns` → `ReturnOut` (request a return),
 *  - `GET  /orders/{id}/returns` → the order's returns (client-side filtered
 *    from the cursor-paginated `GET /returns` list — there is no per-order list
 *    endpoint on the backend).
 *
 * `ReturnOut` already speaks the FE view-model shape (`CamelModel` keeps
 * snake_case, ADR-0039), so no adapter mapping is needed. The DIRECT out-of-
 * window request surfaces as `409 return_window_closed`; the agent-assisted path
 * yields `hitl_pending` — both flow straight through the canonical envelope so
 * the UI can branch on the error `code` / the `status`.
 */
export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  const parsed = await readJson<ReturnCreate>(request);
  if ("response" in parsed) return parsed.response;

  try {
    const env = await apiFetch<ReturnOut>(`/orders/${id}/returns`, {
      method: "POST",
      body: parsed.body,
      token: auth.token,
    });
    return NextResponse.json(env, { status: 201 });
  } catch (err) {
    return toErrorResponse(err, "Could not start the return.");
  }
}

export async function GET(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  try {
    const env = await apiFetch<ReturnOut[]>("/returns", {
      token: auth.token,
      init: { cache: "no-store" },
    });
    const data = (env.data ?? []).filter((r) => r.order_id === id);
    const envelope: Envelope<ReturnOut[]> = {
      data,
      meta: { next_cursor: null, limit: data.length, total: data.length },
    };
    return NextResponse.json(envelope);
  } catch (err) {
    return toErrorResponse(err, "Could not load returns.");
  }
}
