import type { MessageRequest } from "@/lib/api-types";
import { buildScenario } from "@/lib/mock/agent-scenarios";
import { scenarioToStream, wantsInstant } from "@/lib/mock/sse";

/**
 * MOCK `POST /agent/conversations/{id}/messages` → SSE stream (200).
 *
 * Follow-up turns in an existing conversation. Same locked event protocol and
 * scenario engine as the start handler; the contract also requires an
 * `Idempotency-Key` header on this route, which the SSE client sends — the mock
 * accepts it but does not need to dedupe. See conversations/route.ts for the
 * mock posture and the W3 flip-to-live note.
 */
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  let body: MessageRequest;
  try {
    body = (await request.json()) as MessageRequest;
  } catch {
    return Response.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  const { frames } = buildScenario(body.message ?? "");
  return scenarioToStream(frames, { instant: wantsInstant(request) });
}
