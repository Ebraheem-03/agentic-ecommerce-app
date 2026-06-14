"""RAGAS-style evaluation harness for the Hearth agent RAG layer (US-E7-00).

WHAT THIS PACKAGE IS
====================
A small, provider-agnostic library that scores the agent's RAG quality against the
labelled golden set (``docs/qa/eval/golden-v0.jsonl``) on the four headline RAGAS
metrics: **context precision**, **context recall**, **response relevancy**, and
**faithfulness**.

THE CI-SAFE DEFAULT PATH (no keys, no network)
==============================================
The default path runs **deterministically with NO LLM keys** so it is CI-safe:

* context precision/recall are computed by pure set-overlap math (no judge needed) —
  the SAME formula the retrieval smoke uses, factored into :mod:`app.eval.metrics`.
* response relevancy/faithfulness are the LLM-judge metrics, but they run behind a
  ``Judge`` Protocol whose **default** is a :class:`~app.eval.judge.DeterministicJudge`
  — a reproducible lexical-overlap heuristic that EXERCISES the harness end-to-end. It
  is a *harness-exercising stub, not a semantic judge*; its scores are not a quality
  signal, only proof the pipeline runs and is well-formed.
* the per-question ``answer`` the judge metrics need comes from a stub
  :class:`~app.eval.answerer.StubAnswerer` (no live agent runtime exists yet).

THE ONE-LINE REAL-JUDGE SWAP
============================
Mirrors the embedding/retriever house seams (``get_embedder`` / ``get_retriever``):
a real Claude judge registers in ``app.eval.judge._JUDGES`` and is selected by flipping
``EVAL_JUDGE``; a real agent answerer registers in ``app.eval.answerer._ANSWERERS`` and
is selected by ``EVAL_ANSWERER``. No call site changes. Per CLAUDE.md the eval JUDGE is
separate from the runtime PRODUCT LLM (Groq/Gemini free-tier) and, when keys land,
defaults to the latest Claude model (e.g. ``claude-opus-4-8``).

See ``docs/decisions/0030-ragas-harness.md`` for the full rationale.
"""

from __future__ import annotations
