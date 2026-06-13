# infra/

Infrastructure and deploy assets for the agentic AI e-commerce demo.

| Path | Purpose |
|------|---------|
| `db/init/` | Postgres init SQL, mounted into the `db` container to enable extensions on first boot |

Deploy targets (Vercel for web, Render/Fly.io for api, Supabase/Neon for db) and their
configuration land in later weeks. The local stack is defined by the root `docker-compose.yml`.
