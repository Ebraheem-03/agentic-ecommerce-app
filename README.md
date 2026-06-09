# Agentic AI E-Commerce

A full-stack **agentic** e-commerce demo built as a portfolio project. The goal is craft and
learning, not market launch: a clean, typed, container-first stack with an LLM agent layer
woven into the shopping, support, and merchandising flows.

## Stack

| Layer | Technology | Hosting |
|-------|-----------|---------|
| Web | Next.js (TypeScript, strict) | Vercel |
| API | FastAPI (Python, type-checked, Pydantic v2) | Render / Fly.io |
| Database | Postgres + pgvector | Supabase / Neon |
| Local dev | Docker + docker-compose | — |
| Runtime LLM | Groq or Gemini (free tier) | — |

> The runtime LLM (Groq/Gemini) powers the product's own agent layer. Claude Code is used only
> as the build assistant and is not part of the deployed application.

## Repo structure

```
.
├── web/                 # Next.js frontend (TypeScript, strict)
├── api/                 # FastAPI backend (Python, type-checked)
├── infra/               # Compose, DB init scripts, deploy assets
│   └── db/init/         # Postgres init SQL (enables pgvector)
├── docs/                # Roadmap, plan, status, ADRs, daily log
├── .github/workflows/   # CI/CD (GitHub Actions)
├── docker-compose.yml   # Brings up web + api + db locally
├── .env.example         # Template for local env (never commit real .env)
└── LICENSE
```

## Quickstart (local)

Requires Docker and Docker Compose.

```bash
# 1. Copy env template and adjust if needed
cp .env.example .env

# 2. Bring up the full stack (web + api + Postgres/pgvector)
docker compose up --build

# 3. Verify
#    web → http://localhost:3000
#    api → http://localhost:8000/health   -> {"status":"ok"}
#    db  → localhost:5432 (Postgres + pgvector)
```

To validate compose syntax without starting containers:

```bash
docker compose config
```

## Development status

Early scaffold. `web/` and `api/` are intentionally minimal — a placeholder page and a
`GET /health` endpoint — so the container/CI foundation can be built and exercised before the
full application lands in later weeks. See `docs/STATUS.md` for current progress and
`docs/plan/` for the week-by-week plan.

## License

See [LICENSE](./LICENSE).
