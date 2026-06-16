import { NextResponse } from "next/server";
import type { Envelope, NudgeOut } from "@/lib/api-types";
import { acceptNudge } from "@/lib/mock/seller";

// MOCK until the returns/seller backend lands (Day-22 scope call; ADR-0040).
/**
 * MOCK `POST /seller/nudges/{id}/accept` → `NudgeOut` (200) — accept a
 * merchandising nudge (audited, reversible). Mutates the shared mock seller
 * store (ADR-0037). At the W3 gate this proxies the contract endpoint with the
 * `Idempotency-Key` header passed through server-side.
 */
export async function POST(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  const nudge = acceptNudge(id);
  if (!nudge) {
    return NextResponse.json(
      { error: { code: "not_found", message: "That nudge no longer exists.", details: null } },
      { status: 404 },
    );
  }
  const envelope: Envelope<NudgeOut> = { data: nudge, meta: null };
  return NextResponse.json(envelope);
}
