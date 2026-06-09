# CLAUDE.md — Agentic AI E-Commerce (portfolio build)

> This file is loaded into context **every session**. Keep it lean. Never paste the plan,
> task lists, or code here. It is a constitution + index, not a notebook.

## 1. What this is
Full-stack **agentic** e-commerce demo (portfolio, not market-bound — optimize for craft + learning).
Stack: **Next.js → Vercel** · **FastAPI (Python)** · **Postgres + pgvector** · **Docker**.
Runtime LLM (inside the product): **Groq or Gemini** (free tier). Build assistant: **Claude Code**.
Timeline: **~4 weeks**, daily commits.

## 2. Golden rules (apply every session)
- Load context **on demand**: read only `docs/plan/<current-day>.md` plus the files for the task in hand. Never read the whole plan or whole repo.
- Stable rules live here; transient work stays in the session. Record state in `docs/STATUS.md`, **not** in this file.
- Delegate layer work to the matching subagent (§4) to keep the main thread's context clean.
- One feature = one branch = one PR. Commit at least once per day.
- If a task is tagged `[REVIEW]` or `[DECISION]`, stop and ask the human. If `[AFK]`, take it to done + commit.

## 3. Repo & doc map
| Path | Purpose | When to read |
|---|---|---|
| `docs/plan/roadmap.md` | Epics + 4-week schedule | once, at week start |
| `docs/plan/week-N.md` | Day-wise user stories: id, story, estimate, date, owner agent, autonomy, acceptance criteria | current day only |
| `docs/STATUS.md` | Single source of truth for "where we are" | start of session; update at end |
| `docs/DAILY-LOG.md` | One line/day: shipped, blocked | append daily |
| `docs/decisions/*.md` | Short ADRs for non-obvious choices | when revisiting a decision |
| `.claude/agents/*.md` | Full system prompt per agent | this file only indexes them |
| `.claude/skills/*/SKILL.md` | Installed skills — **source of truth for usage** | when the skill is invoked |

## 4. Agent roster
Full brief per agent lives in `.claude/agents/<name>.md`. **Communication is hub-and-spoke through Atlas.**
Subagents have **isolated, non-shared context/memory** — they never talk to each other directly. All cross-agent
state passes through repo artifacts (`STATUS.md`, ADRs, PR descriptions).

| Agent | Designation | Owns | Autonomy |
|---|---|---|---|
| **Atlas** | Tech Lead / Orchestrator | Planning, delegation, integration, PR review, all human conversation | needs you for scope & priority calls |
| **Nova** | Brand & UI Designer | Branding, logo, color/type system, Figma-style screens | `[REVIEW]` — your taste required |
| **Iris** | Frontend Engineer | Next.js app, components, state, accessibility | `[AFK]` build · `[REVIEW]` UX choices |
| **Orion** | Backend Engineer | FastAPI, Pydantic models, business logic, Scalar API docs | mostly `[AFK]` |
| **Sable** | Database Engineer | Postgres schema, migrations, pgvector, seed data | mostly `[AFK]` |
| **Echo** | AI / Agents Engineer | The product's own agent layer (shopping/support/merchandising), RAG, tools, guardrails, Groq/Gemini wiring | `[AFK]` build · `[REVIEW]` prompt/guardrail policy |
| **Juno** | QA & Integration | Unit/integration/e2e tests; verifies integration branches; gates PRs | `[AFK]` |
| **Rhea** | DevOps | Docker, docker-compose, CI/CD (GitHub Actions), env/secrets, deploy | `[AFK]` · `[REVIEW]` before prod |

> You may collapse **Sable into Orion** if you want a smaller roster. Do not add agents beyond this without a reason.

## 5. How work flows & how you see progress
1. Atlas reads the current day's plan file, assigns each story to its owner agent, runs it, reviews the output.
2. Each agent works in its own context, commits to a feature branch, updates `docs/STATUS.md`, and returns a **short** summary to Atlas (not its full transcript — saves tokens).
3. Atlas posts an end-of-session chat summary: **shipped / in-progress / blocked / needs-your-decision**.
4. You can always see progress without re-explaining anything via three artifacts: `docs/STATUS.md`, `docs/DAILY-LOG.md`, and open PR descriptions.

## 6. Skills — who uses each, and when
| Skill | Used by | Use it for |
|---|---|---|
| **Google Stitch** | Nova only | Design phase: branding, logo directions, screen layouts — **before** any frontend code. Output feeds Iris. |
| **21st.dev (Magic)** | Iris | Source/compose preferred components; don't hand-roll what 21st already provides. |
| **Impeccable** | Iris | The build standard for all production UI — structure, polish, consistency. |

Always defer to each skill's own `SKILL.md` for exact mechanics; this file only says **who** reaches for it and **when**.

## 7. Engineering standards
- Backend: **Pydantic v2** models for every request/response; API docs served with **Scalar** (not Swagger UI).
- Strict typing: TS strict on frontend; type-checked Python backend.
- Tests ship **with** each feature; Juno gates the PR. No merge to `dev` without green CI.
- Secrets in env only, never committed; keep `.env.example` current.

## 8. Git & CI/CD
- Branch flow: `feature/<module>-<slug>` → `integration/<module>` → **PR into `dev`** → after QA + green CI → **PR `dev` → `main`**.
- Conventional Commits (`feat:`, `fix:`, `chore:` …). Daily commits. Semver tags on `main`.
- GitHub Actions on every PR to `dev`: lint · type-check · test · docker build. On `dev` merge: deploy dev/staging. On `main`: deploy prod.
- Promotion order is **local → dev → prod**. Never skip a stage.

## 9. Deploy targets (free tier)
Frontend: **Vercel** · Backend (dockerized): **Render** or **Fly.io** · DB: **Supabase** or **Neon** (Postgres + pgvector).
A single `docker-compose.yml` must bring up the full stack locally (web + api + db).

Atlas must maintain docs/PROGRESS.md as a live event log. Every delegated agent run must log: timestamp, agent, story ID, action, status, files touched, tests run, and next step. STATUS.md stays the compact current-state board; PROGRESS.md is the detailed execution timeline.
