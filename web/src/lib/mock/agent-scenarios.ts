import type {
  Citation,
  DoneEvent,
  ErrorBody,
} from "@/lib/api-types";
import { findProduct, toRecommendation } from "@/lib/mock/catalog";

/**
 * MOCK Ember scenario engine — scripts the locked SSE turn (`token → citations
 * → done`, or `error`) the route handlers emit while the real agent loop lives
 * on `integration/agents`. The event ORDER and payload TYPES are the contract
 * (ADR-0021); the strings here are placeholder. Keyed off the prompt so the
 * US-QA-D19 E2E can deterministically drive each path:
 *
 *  - prompt contains "refuse" / "ignore your"  → REFUSAL turn (agent-refusal-notice)
 *  - prompt contains "?" with no budget cue, or "which"/"either"/"or" → CLARIFY
 *  - prompt contains "boom" / "error"          → mid-stream ERROR frame
 *  - otherwise                                 → RECOMMEND turn with cards + why
 *
 * A scenario is a flat list of timed frames the route turns into `text/event-stream`.
 */

export type ScriptFrame =
  | { kind: "token"; delta: string; delayMs: number }
  | { kind: "citations"; citations: Citation[]; delayMs: number }
  | { kind: "done"; done: DoneEvent; delayMs: number }
  | { kind: "error"; error: ErrorBody; delayMs: number };

export type ScenarioKind = "recommend" | "clarify" | "refusal" | "error";

function tokens(text: string, perChunkMs = 28): ScriptFrame[] {
  // Split into word-ish chunks so the stream reads like real generation.
  return text
    .split(/(\s+)/)
    .filter((c) => c.length > 0)
    .map((delta) => ({ kind: "token" as const, delta, delayMs: perChunkMs }));
}

function pickScenario(prompt: string): ScenarioKind {
  const p = prompt.toLowerCase();
  if (/(ignore your|disregard|system prompt|reveal|jailbreak|refuse|illegal|weapon)/.test(p)) {
    return "refusal";
  }
  if (/\b(boom|trigger error|cause error)\b/.test(p)) return "error";
  if (
    /\b(which|either|this or that|or the)\b/.test(p) ||
    (p.includes("?") && !/\$|\bunder\b|\bbudget\b|\baround\b/.test(p))
  ) {
    return "clarify";
  }
  return "recommend";
}

const CONV_ID = "conv_mock";

function recommendScenario(): ScriptFrame[] {
  const bowl = findProduct("prod_bowl");
  const mugs = findProduct("prod_mug_pair");
  const recs = [
    bowl &&
      toRecommendation(
        bowl,
        "Right at budget, and the one piece a cooking couple will reach for at every dinner. Food-safe glaze, dishwasher-fine.",
      ),
    mugs &&
      toRecommendation(
        mugs,
        "If you'd rather give a pair, this comes in under budget and matches the bowl's maker glaze family.",
      ),
  ].filter((r): r is NonNullable<typeof r> => Boolean(r));

  const citations: Citation[] = [
    {
      source_type: "product",
      source_id: "prod_bowl",
      chunk_index: 0,
      snippet: "Food-safe and dishwasher-fine; generous enough for a salad to share.",
      score: 0.86,
    },
    {
      source_type: "product",
      source_id: "prod_mug_pair",
      chunk_index: 0,
      snippet: "A pair of hand-thrown stoneware mugs in a warm ember glaze.",
      score: 0.79,
    },
  ];

  const done: DoneEvent = {
    conversation_id: CONV_ID,
    message_id: "msg_rec",
    action: { kind: "recommend", outcome: "applied" },
    recommendations: recs,
    clarify: null,
    refusal: null,
  };

  return [
    ...tokens(
      "Here's what I'd give. For a cooking couple at around $90, I leaned toward pieces that get used daily and read as a set. Two picks, with why:",
    ),
    { kind: "citations", citations, delayMs: 160 },
    { kind: "done", done, delayMs: 120 },
  ];
}

function clarifyScenario(): ScriptFrame[] {
  const done: DoneEvent = {
    conversation_id: CONV_ID,
    message_id: "msg_clarify",
    action: { kind: "clarify", outcome: null },
    recommendations: [],
    clarify:
      "Happy to narrow it down. Is this for everyday use or more of a special-occasion gift, and do you have a rough budget in mind?",
    refusal: null,
  };
  return [
    ...tokens(
      "I can point you to the right piece, I just need one detail to avoid guessing.",
    ),
    { kind: "done", done, delayMs: 120 },
  ];
}

function refusalScenario(): ScriptFrame[] {
  const citations: Citation[] = [
    {
      source_type: "policy",
      source_id: "policy_scope",
      chunk_index: 2,
      snippet: "Hearth's assistant answers questions about the catalogue, makers, orders, and returns.",
      score: 0.91,
    },
  ];
  const done: DoneEvent = {
    conversation_id: CONV_ID,
    message_id: "msg_refuse",
    action: { kind: "refuse", outcome: "refused" },
    recommendations: [],
    clarify: null,
    refusal:
      "That's outside what I can help with. I'm here for the Hearth catalogue, makers, your orders, and returns, and I won't step outside that or around our policies.",
  };
  return [
    ...tokens("I have to stop you there."),
    { kind: "citations", citations, delayMs: 140 },
    { kind: "done", done, delayMs: 120 },
  ];
}

function errorScenario(): ScriptFrame[] {
  return [
    ...tokens("Let me look through the catalogue"),
    {
      kind: "error",
      error: {
        code: "internal_error",
        message: "The assistant lost its connection mid-thought. Please try again.",
        details: null,
      },
      delayMs: 180,
    },
  ];
}

export function buildScenario(prompt: string): {
  kind: ScenarioKind;
  frames: ScriptFrame[];
} {
  const kind = pickScenario(prompt);
  switch (kind) {
    case "clarify":
      return { kind, frames: clarifyScenario() };
    case "refusal":
      return { kind, frames: refusalScenario() };
    case "error":
      return { kind, frames: errorScenario() };
    case "recommend":
    default:
      return { kind, frames: recommendScenario() };
  }
}
