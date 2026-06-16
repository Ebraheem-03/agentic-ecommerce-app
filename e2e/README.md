# E2E test harness

Top-level Playwright workspace that drives **web + api + agent** flows from one
place (search → cart → checkout → order → status, plus edge paths). Kept here
rather than inside `web/` so a single suite can navigate the browser *and* hit
the API / agent endpoints without coupling to the frontend package.

## Commands

Run from this directory (`e2e/`):

```bash
npm install            # one-time: installs @playwright/test + dotenv
npx playwright install # one-time: downloads browser binaries
npm run e2e            # run the full suite (boots the web app via webServer)
npm run e2e:smoke      # @smoke only — server-free harness/env checks (no app boot)
npm run e2e:web        # @web browser smoke — self-boots web, desktop + mobile
npm run e2e:ui         # interactive UI mode
npm run e2e:report     # open the last HTML report
```

### Lanes

- **`@smoke` (US-QA-D01)** — harness + env-contract checks that pass with **no
  running server**. `e2e:smoke` sets `E2E_NO_WEBSERVER=1` so Playwright does not
  boot the web app, preserving the Day-1 "smoke stays green with no server"
  invariant (ADR-0012).
- **`@web` (US-QA-D18)** — browser smoke: boots the Next.js app (`next build &&
  next start`, pinned port `3100`) and asserts **route health**, the **auth
  screens**, the **app shell**, and an **axe a11y baseline** (zero serious/critical
  on `/`, `/login`, `/register`). It is **backend-free**: static/SSR render + the
  signed-out shell, not real auth round-trips. Runs on **two viewport projects**,
  `desktop-chromium` (Desktop Chrome) and `mobile-chromium` (Pixel 5), so every
  `@web` test executes twice. Browsers: `npx playwright install --with-deps chromium`.
- **`J-*` journeys (US-QA-D03)** — still `test.fixme`; they need the integrated
  backend and flip on later.

## Env contract

E2E targets are configured via env vars, documented in
[`.env.example`](./.env.example). Copy it to `e2e/.env` to override locally:

| Var            | Purpose                                  | Default                 |
| -------------- | ---------------------------------------- | ----------------------- |
| `WEB_BASE_URL` | Base URL of the Next.js web app          | `http://localhost:3000` |
| `API_BASE_URL` | Base URL of the FastAPI service          | `http://localhost:8000` |

Resolution order (see `playwright.config.ts`): **real process env → `e2e/.env`
→ `e2e/.env.example`**. CI can inject real values; the example file is the
zero-setup fallback so the smoke always resolves the contract.

## Layout

```
e2e/
├── playwright.config.ts   # config + env loading; exports WEB/API base URLs
├── tests/
│   ├── _selectors.ts       # typed data-testid registry (mirrors docs/qa/test-ids.md)
│   ├── smoke.spec.ts       # @smoke (no server) — keeps CI green with no app up
│   └── J-*.spec.ts         # one spec per journey ID (US-QA-D03 skeletons)
├── .env.example            # env contract (committed); copy to .env locally
├── package.json            # the `e2e` command lives here
└── tsconfig.json
```

## Journey specs (US-QA-D03)

Each `J-*` journey in [`docs/qa/qa-matrix.md`](../docs/qa/qa-matrix.md) §2 maps
**1:1** to a spec file named by its ID (`J-BUY-01.spec.ts`, `J-SEL-04.spec.ts`, …).
Today they are **skeletons**: every test is `test.fixme(...)`, so they are
discovered and type-checked but **never executed** — `npm run e2e:smoke` and the
server-free CI job stay green. Each test references stable selectors from
`tests/_selectors.ts` (the typed mirror of `docs/qa/test-ids.md`) and the scenario
steps from the matrix.

To activate a journey once web + api scaffold exists: add a `webServer` block to
`playwright.config.ts`, then flip that spec's `test.fixme` → `test`. Until then,
selectors are a **contract** Iris/Nova build against; the specs do not run.
