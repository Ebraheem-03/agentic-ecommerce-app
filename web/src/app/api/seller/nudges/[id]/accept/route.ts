import { NextResponse } from "next/server";
import type { NudgeAcceptRequest, NudgeOut } from "@/lib/api-types";
import { apiFetch } from "@/lib/api";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `POST /seller/nudges/{id}/accept` → `NudgeOut` (Day-24 flip-to-live,
 * ADR-0040). Accept a merchandising nudge (audited, reversible, idempotent).
 * `nudge_id == product_id` (Echo: ≤1 live nudge/product). The optional
 * `idempotency_key` is forwarded from the body. `NudgeOut` already matches the
 * FE view-model (the display-only `accepted` flag is set client-side once the
 * accept resolves), so no adapter mapping is needed.
 */
export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  const parsed = await readJson<NudgeAcceptRequest>(request);
  if ("response" in parsed) return parsed.response;

  try {
    const env = await apiFetch<NudgeOut>(`/seller/nudges/${id}/accept`, {
      method: "POST",
      body: parsed.body ?? {},
      token: auth.token,
    });
    // The dashboard card surfaces an `accepted` marker client-side; the backend
    // doesn't carry the flag, so set it here on the way out.
    const data: NudgeOut = { ...env.data, accepted: true };
    return NextResponse.json({ data, meta: env.meta ?? null });
  } catch (err) {
    return toErrorResponse(err, "Could not accept the nudge.");
  }
}
