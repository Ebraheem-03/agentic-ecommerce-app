# ADR-0005: Runtime LLM: Groq or Gemini (free) with routing + fallback

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
The product's agents need an LLM; cost must stay at zero for now. (Build-time assistant is Claude Code — separate concern.)

## Decision
Echo wires a provider-routing layer over Groq and Gemini free tiers with automatic fallback and a semantic cache.

## Consequences
Free tiers are rate-limited; the cache and routing mitigate this. Provider keys are a [REVIEW] item the human supplies.
