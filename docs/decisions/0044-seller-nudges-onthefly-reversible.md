# ADR-0044 — Seller merchandising nudges: on-the-fly model + audit-row reversibility

Status: accepted · Day 24 (W4D3) · Owner: Echo

## Context
`GET /seller/nudges` + `POST /seller/nudges/{id}/accept` (J-SEL-03/04) surface agent-backed
merchandising suggestions for a seller's own catalog. The FE (Day 20) expects an "audited,
reversible accept". We had to choose a persistence model and a reversibility mechanism.

## Decision
1. **Nudges are generated ON THE FLY — no `seller_nudges` table.** A nudge is the
   seller-facing surfacing of a grounded re-price suggestion computed from the catalog at
   read time. It reuses Echo's Day-17 merch agent grounding core verbatim
   (`app.agent.merch.find_comparables` + `suggest_price`) — NOT a parallel brain. Comparables
   EXCLUDE the seller's own store so a product is priced against the wider market; the
   suggested price is the comparables' median, surfaced with its basis. No invented data.

2. **`nudge_id` = the product id.** A product has at most one live re-price nudge (its current
   cheapest-active price vs. the grounded median), so the id is stable and deterministic.
   `accept` re-resolves + RE-GROUNDS by product id — it never trusts a stale client-side
   suggested price, so an accept can't be steered to an arbitrary number.

3. **Reversibility rides on `agent_actions`, no extra table.** Accept writes one
   `action_type='merch_nudge_accept'`, `outcome='applied'` row whose payload snapshots the
   PRIOR per-variant prices (`prior_variant_prices`) plus the applied price + basis. An undo
   is a pure replay of that snapshot. This is lighter than a nudge/version table and keeps the
   audit trail the single source of truth the FE reads.

## Scope + guardrails
- Identity/scope from `require_user` -> the caller's OWN store; a foreign/unknown/non-active
  product 404s as "nudge" (no existence leak). The market moving so a product no longer
  warrants a nudge also 404s (nothing to apply).
- The only seller-supplied free field is the optional `idempotency_key`; it is scanned with
  `scan_for_injection` before use — a hit is logged as an `action_type='guardrail'`,
  `outcome='refused'` row and rejected 422 (no mutation). The retrieval brief is built from
  the seller's OWN existing listing copy, so there is no untrusted free text at nudge time.
- Accept is idempotent via `app.services.idempotency` (endpoint `seller:nudge_accept:{id}`):
  a replay re-emits the stored `NudgeOut` without re-applying the price.

## Consequences
- No migration (no new head). The `0007_semantic_cache` table-count contract is unchanged.
- A nudge reflects the live catalog every read — no staleness/regeneration story to manage.
- A future explicit "undo" endpoint can replay `merch_nudge_accept` payloads directly.
- No new `ErrorCode` — reuses `not_found` (404) and `validation_error` (422, injection).
