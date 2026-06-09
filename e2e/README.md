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
npm run e2e            # run the full suite
npm run e2e:smoke      # run only @smoke-tagged specs (no app server needed)
npm run e2e:ui         # interactive UI mode
npm run e2e:report     # open the last HTML report
```

> Day 1 (US-QA-D01) ships the harness + a smoke placeholder only. The browser
> install / heavy deps are **not** run yet — declaring scripts, deps and config
> is enough. The smoke passes with **no running server**.

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
│   └── smoke.spec.ts       # @smoke (no server) + fixme stubs for US-QA-D03
├── .env.example            # env contract (committed); copy to .env locally
├── package.json            # the `e2e` command lives here
└── tsconfig.json
```

Real navigation specs land in **US-QA-D03**; that story also adds a `webServer`
block to the config to spin up web + api for those specs.
