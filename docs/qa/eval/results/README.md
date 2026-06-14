# Eval results — captured smoke artifacts

Machine-readable outputs of the eval smokes (US-QA-D10 onward). These are **captured
baselines**, committed on purpose so progress is reviewable in git.

## `retrieval-smoke-<date>.json` + `retrieval-smoke-latest.json`

Written by `api/tests/qa/test_retrieval_smoke.py` — the no-LLM RAGAS **retrieval-half**
smoke over the product-grounded golden items, against the live keyword `GET /search`.
`retrieval-smoke-latest.json` always points at the most recent run (Echo's Week-4
semantic-retrieval comparison baseline). Dated files are the per-run history.

Each artifact carries: `scores` (mean precision@k / recall@k), `scope` (in-scope vs
policy-only excluded, failing-sample count), per-item precision/recall, and the full
`failing_samples` log (question + expected slugs + retrieved top-k).

**v0 (keyword) headline:** mean precision@5 / recall@5 = **0.000** across 17/25 in-scope
items. This is the EXPECTED keyword result, not a failure — `websearch_to_tsquery` ANDs
every token of a raw natural-language question, so question-phrased queries match nothing.
It is the precise gap semantic retrieval closes; see `docs/qa/eval/README.md` for the
full framing. The smoke is informational, NOT a CI gate.
