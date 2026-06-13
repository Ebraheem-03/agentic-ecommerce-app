# Contributing

This is an agentic-AI e-commerce **portfolio build**. Work is orchestrated by **Atlas** (tech lead)
and delegated to specialist agents (Nova, Iris, Orion, Sable, Echo, Juno, Rhea). Humans set scope and
make `[REVIEW]`/`[DECISION]` calls. See `CLAUDE.md` for the full constitution.

## Branching model

```
feature/<module>-<slug>  →  integration/<module>  →  dev  →  main
```

- **`feature/<module>-<slug>`** — one branch per story/feature. Branched from its `integration/<module>`.
- **`integration/<module>`** — collects all feature branches for a module (e.g. `integration/foundations`,
  `integration/design`, `integration/data`, `integration/backend`).
- **`dev`** — integration target. Reached only by **PR** from `integration/<module>`, after Juno QA + green CI.
- **`main`** — release branch. Reached only by **PR** from `dev`. Tagged with semver (`vMAJOR.MINOR.PATCH`).

Promotion order is **local → dev → prod**. Never skip a stage. One feature = one branch; one module
integration = one PR into `dev`. See `docs/decisions/0007-branching-strategy.md`.

## Commits — Conventional Commits

Format: `type(optional-scope): subject` — imperative, lower-case, no trailing period.

| Type | Use for |
|---|---|
| `feat` | a new user-facing capability |
| `fix` | a bug fix |
| `chore` | tooling, scaffolding, deps, no product behavior |
| `docs` | documentation only |
| `test` | adding or fixing tests |
| `refactor` | code change that neither fixes a bug nor adds a feature |
| `ci` | CI/CD pipeline changes |
| `build` | build system / Docker changes |

- Commit **at least once per day**; commit when a story is done (one logical commit per story).
- Reference the story id in the body when useful, e.g. `Refs: US-E1-03`.

## Pull requests

- PRs target **`dev`** from an `integration/<module>` branch (not from individual feature branches).
- A PR description states: what shipped, the stories it closes, how it was tested, and any follow-ups.
- **CI must be green** (lint · type-check · test · docker build) and **Juno must sign off** before merge.
- PR `dev → main` is the release; tag semver on `main` after merge.

## Engineering standards (summary — full list in `CLAUDE.md §7`)

- Backend: **Pydantic v2** for every request/response; API docs via **Scalar**. Python is type-checked.
- Frontend: **TypeScript strict**.
- Tests ship **with** each feature. No merge to `dev` without green CI.
- Secrets live in env only, never committed. Keep `.env.example` current.

## Where state lives

| Artifact | Purpose |
|---|---|
| `docs/STATUS.md` | Compact current-state board (Done / In-progress / Blocked / Needs-decision). |
| `docs/PROGRESS.md` | Append-only execution log; every agent run records its entry. |
| `docs/DAILY-LOG.md` | One line per day: shipped / blocked. |
| `docs/decisions/*.md` | Short ADRs for non-obvious choices. |
