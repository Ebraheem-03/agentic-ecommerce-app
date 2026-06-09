# ADR-0008: Hub-and-spoke agent orchestration (siloed subagent memory)

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
Claude Code subagents each run in an isolated context and do not share memory with one another.

## Decision
Atlas (the lead/main thread) is the only hub. Specialists never communicate directly; all shared state flows through STATUS.md, ADRs, and PR descriptions. Each story is delegated with the smallest possible brief.

## Consequences
Prevents context pollution and saves tokens; requires Atlas to carry cross-agent context deliberately.
