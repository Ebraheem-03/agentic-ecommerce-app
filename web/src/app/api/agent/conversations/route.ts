import type { ConversationStartRequest } from "@/lib/api-types";
import { buildScenario } from "@/lib/mock/agent-scenarios";
import { scenarioToStream, wantsInstant } from "@/lib/mock/sse";

/**
 * MOCK `POST /agent/conversations` → SSE stream (201/200).
 *
 * Starts a conversation and streams the assistant turn as `text/event-stream`
 * (`token → citations → done`, or a terminal `error`) per the locked contract
 * (ADR-0021, contract-v0.md §"Agent SSE event protocol"). The real agent loop
 * (retrieve → ground → act → persist) lives on `integration/agents`; this mock
 * serves the same wire shape so the docked panel + US-QA-D19 E2E run end-to-end
 * now. At the W3 gate, point `NEXT_PUBLIC_AGENT_STREAM_BASE` at the live API and
 * this handler is bypassed — the SSE client is unchanged.
 *
 * Scenario is keyed off the prompt (see agent-scenarios.ts) so QA deterministically
 * drives recommend / clarify / refusal / error. Append `?instant=1` for no-delay.
 *
 * NOTE for Atlas: this is intentionally a mock surface. The `force-dynamic` /
 * no-store posture keeps Next from trying to statically cache the stream.
 */
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  let body: ConversationStartRequest;
  try {
    body = (await request.json()) as ConversationStartRequest;
  } catch {
    return Response.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  const { frames } = buildScenario(body.message ?? "");
  return scenarioToStream(frames, { instant: wantsInstant(request) });
}
