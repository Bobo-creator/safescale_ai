# Spec: app

Module id: `app` (see [CAPABILITY_MAP.md](CAPABILITY_MAP.md)).
Depends on: `hazard-analysis`, `explain`. This is the MVP the brief describes: "the dashboard
presents the closest historical matches, hazard signals, evidence cards, and recommended areas for
engineering investigation."

## Objective

A public web app where an engineer pastes a product description and, within about 2 seconds, sees
the historical hazard picture. A cited plain-language explanation follows a few seconds later.

**User flow**

1. Type or pick an example description (e.g. the brief's night light) and press *Analyze*.
2. **About 1–2 s later:** the signal (LOW / MODERATE / HIGH and what drives it), the hazard profile
   (bars showing the share of similar recalls, with the multiple of that hazard's rate among all
   recalls), shared and failure terms, investigation areas, cited standards, and **evidence cards**
   for the similar recalls (title, date, similarity, hazard labels, evidence phrase, CPSC link;
   weak matches visibly marked).
3. **About 8–10 s later** (with a visible progress state): the explanation (summary, hazards, why
   these match, investigation notes). Every `[#id]` citation jumps to and highlights its evidence card.
4. The disclaimer and the statistical caveat are always visible, not hidden in a footer.
5. Options: depth k = 25 / 50 / 100; under "Advanced", the retrieval method (vector / keyword /
   hybrid), so the seminar can show the methods side by side.

**Done looks like:** `https://<project>.vercel.app` runs the night-light example end to end on
the production data, on desktop and phone.

## Key facts (checked 2026-10-19)

- **Vercel services:** one project can hold a Next.js frontend and a FastAPI backend, with rewrites
  routing `/api/*` to the backend and everything else to the frontend. Python functions bundle up
  to 500 MB, and `maxDuration` is configurable.
- **Our Python code is reused as is.** The FastAPI app lives in the existing package
  (`safescale.api:app`) and calls the same `analyze()` and `explain()` the CLI uses.
- **Measured costs per request:** analysis ≈ 58 ms of database work in 8 queries, plus 1 embedding
  call (≈ 0.6 s); explanation ≈ 8–10 s and ≈ $0.0009. From a laptop the round trips add ~350 ms.
  Vercel's `iad1` region (us-east) sits next to Supabase `us-east-1`, so they should mostly disappear.
- **Supabase free tier pauses after about a week idle** (it happened on 2026-10-19). A daily health
  ping keeps it awake.

## Design

(Example descriptions live in the frontend as a static list, so they render instantly; there is
no `/api/examples` endpoint.)

### Architecture

```
Browser ──► Vercel (iad1)
              ├── web/        Next.js (App Router, TypeScript, Tailwind)     /*
              └── pipeline/   FastAPI service  safescale.api:app             /api/*
                                   │  analyze() / explain()
                                   ├──► Supabase Postgres (transaction pooler, role safescale_app)
                                   └──► OpenAI (embeddings + explanation)
```

### API (FastAPI)

| Endpoint | Body | Returns | Notes |
|---|---|---|---|
| `POST /api/analyze` | `{query, k, method}` | `HazardReport.to_dict()` | the fast path |
| `POST /api/explain` | `{query, k, method}` | `{report, explanation}` | recomputes the analysis server-side, so the explanation is always grounded in a report the server built (~0.6 s extra) |
| `GET /api/health` | — | `{ok, db_ms}` | `select 1`; also the daily keep-alive (Vercel cron) |

- **Input validation:** `query` 10–1,000 characters after trimming; `k` ∈ {25, 50, 100};
  `method` ∈ {vector, keyword, hybrid}. Anything else gets a 422 with a clear message.
- **Errors:** if OpenAI fails during `/api/explain`, the response still has the report and the
  deterministic fallback summary (already built in `explain`). If the database fails, the API
  returns a 503 with a retry hint. Stack traces are never sent to the browser.
- **No streaming in v1.** Streaming the explanation would mean showing text before the validator
  has checked it, and the validator is what makes explanations trustworthy. Instead, the page shows
  the analysis right away and the checked explanation when it is ready. Item-by-item streaming
  (validate each sentence as it completes) is a later improvement.

### Database access for the app

- **New least-privilege role `safescale_app`** (created like the pipeline role: a password verifier
  generated locally, the plaintext only in git-ignored `.env` and in Vercel's encrypted
  environment variables). It may `select` the tables and views the analysis reads, execute the
  search functions, and read and write the rate-limit table. Nothing else: no ingest or
  classify, no DDL.
- **Migration `007_app_access.sql`:** row-level security policies `for select to safescale_app
  using (true)` on the read tables (Supabase's `anon` and `authenticated` stay locked out), plus the
  `app_rate_limits` table.
- **Serverless-friendly connection:** Supabase's transaction pooler (port 6543). psycopg runs with
  prepared statements off (`prepare_threshold=None`), which the pooler needs. One small connection
  per warm function instance.

### Abuse and cost protection (the app is public and calls paid APIs)

| Limit | Default | Why |
|---|---|---|
| Analyses per visitor per hour | 30 | an embedding costs ~$0.000002, but the database is free tier |
| Explanations per visitor per hour | 10 | $0.0009 each |
| Explanations per day, all visitors | 300 | caps OpenAI spend at ~$0.30/day |

- A visitor is identified by a salted hash of their IP address (the salt is an env secret). The
  table keeps only `(bucket, window, count)`, never IPs or descriptions.
- Over a limit: analysis returns 429 with "try again in N minutes"; past the daily cap the
  explanation is skipped with a notice, but the analysis still works.
- All limits are env vars. They are a protection, not a business rule.

### Privacy

Product descriptions may be confidential. The app **does not store them**: they aren't in the
database, aren't in request logs (bodies are never logged), and aren't in analytics. They are sent
to OpenAI for the embedding and the explanation; the page says so under the input box. OpenAI does
not train on API data by default.

### Frontend (Next.js)

- **One main page** (`/`): the input panel, then results in this order: signal → hazard profile →
  explanation → investigation areas and standards → evidence cards. Plus an **About** page (`/about`)
  covering methodology, data source and date, what the signal means and doesn't, the hazard
  taxonomy, and the evaluation results so far.
- **Design:** clean, calm and engineering-grade, light and dark themes, readable at phone width.
  The visual design is built with the frontend-design skill, with the 21st component library where
  it fits.
- **Accessibility:** keyboard reachable; the signal isn't conveyed by color alone; chart bars carry
  text values.
- No auth, no saved projects, no file upload in v1 (the brief's nice-to-haves).

### Configuration

| Variable | Where | Notes |
|---|---|---|
| `APP_DATABASE_URL` | Vercel (encrypted) | `safescale_app` via transaction pooler |
| `OPENAI_API_KEY` | Vercel (encrypted) | the same key, or a separate key with its own spend limit (recommended) |
| `RATE_LIMIT_SALT` | Vercel (encrypted) | random |
| `EXPLAIN_MODEL`, `EXPLAIN_REASONING_EFFORT`, limit overrides | Vercel | optional |

## Commands

```bash
# local development
cd pipeline && uv run uvicorn safescale.api:app --reload --port 8000     # API
cd web && npm install && npm run dev                                     # UI at :3000, /api proxied
cd pipeline && uv run pytest                                             # API tests (offline)
cd web && npm run lint && npm run build
npx playwright test                                                      # e2e (see Testing)

# deploy (after you've logged in once with `! vercel login`)
vercel deploy            # preview
vercel deploy --prod     # production
```

## Project structure

```
vercel.json                      # services (web, pipeline), rewrites, cron, region iad1
db/migrations/007_app_access.sql
pipeline/src/safescale/api/
  __init__.py  app.py            # FastAPI app, routes, error handling
  deps.py                        # connection, embedder, explainer (overridable in tests)
  limits.py                      # rate limiting against app_rate_limits
pipeline/tests/api/              # TestClient tests with fakes and the test database
web/                             # Next.js app
  app/page.tsx  app/about/page.tsx
  components/                    # signal, profile chart, evidence card, explanation, …
  lib/api.ts                     # typed client for the API
e2e/                             # Playwright tests
```

## Testing strategy

- **API (pytest, offline):** FastAPI TestClient with the fake embedder and scripted explainer on
  the fixture database. Covers input validation, 429s and the daily cap, the OpenAI-failure fallback,
  the 503 path, no request bodies in logs, and response shapes matching what the UI expects.
- **Database access:** a test confirms `safescale_app` can read what it needs and cannot write
  recalls or run DDL, and that `anon` still can't read anything.
- **UI:** TypeScript strict, lint and build in CI-style local runs. Component behavior (citation
  jump, weak-match marking, error states) is covered by e2e.
- **End to end (Playwright):** locally against the real API on Supabase (real models, about $0.01
  per run), then against the deployed preview. Covers the night-light flow, citation click →
  highlighted card, k / method switches, the unrelated-query notice, a phone-width layout, and keyboard use.
- **Performance check after deploy:** time to the analysis and to the explanation, measured from
  the browser over 10 runs.

## Boundaries

- **Always:** show the disclaimer and caveat with every result. Validate inputs on the server. Keep
  secrets in Vercel env vars and git-ignored `.env`. Rate-limit every endpoint that costs money.
- **Ask first:** creating the `safescale_app` role and the Vercel project (outward-facing).
  Raising the daily explanation cap. Adding analytics or any storage of queries. Adding a custom
  domain.
- **Never:** store or log product descriptions. Show unvalidated model text. Ship the pipeline role
  or the OpenAI key to the browser. Expose a database URL in client code.

## Success criteria

1. The production URL runs the night-light example end to end: analysis, then a validated
   explanation with working citation links, then the disclaimer.
2. **Speed (deployed, warm, from the browser, median of 10):** analysis visible in < 2 s;
   explanation in < 12 s. The cold first request after idle is reported separately.
3. Over-limit requests get 429; past the daily cap there's no explanation but the analysis works;
   no IPs or descriptions in the database.
4. `safescale_app` can't write recalls or run DDL; `anon` can't read any table; advisors show no
   new warnings.
5. Playwright suite passes on desktop and phone width, including the keyboard path.
6. Lighthouse on the deployed home page: accessibility ≥ 95, performance ≥ 90.
7. The Supabase project stays awake (daily health cron), verified a week after launch.

## Decisions (approved 2026-10-19)

- **Vercel:** the owner has an account and will run `! vercel login` once at deploy time.
- **OpenAI key:** the same key as the pipeline (owner's choice). The daily cap of 300 explanations
  (≈ $0.30/day) and the per-visitor limits are the spend guard. A separate key with a spend limit
  remains an easy later change (one env var).
- **Rate limits:** 30 analyses and 10 explanations per visitor per hour; 300 explanations per day.
- **Method selector:** kept, under "Advanced" (vector is the default).

## Results (2026-10-20, production: https://safescale-ai.vercel.app)

| # | Criterion | Result |
|---|---|---|
| 1 | Night-light example end to end on production | ✅ Playwright @smoke (desktop + phone) green: signal, profile, 25 evidence cards, validated explanation, citation jump, disclaimer |
| 2 | Analysis < 2 s, explanation < 12 s (median, warm, from the browser) | ✅ analysis **0.59 s** (0.47–1.05 s, 10 runs); explanation **8.5 s** (6.2–9.6 s, 5 runs; includes the server re-running the analysis). First cold request ≈ 4 s |
| 3 | 429s, daily cap, no IPs or descriptions stored | ✅ tested in pytest; on production the table holds only 40-character salted buckets, and this machine hit its 10 explanations/hour as designed |
| 4 | `safescale_app` can't write or run DDL; `anon` reads nothing; advisors | ✅ verified through the transaction pooler; advisors show only the two intended INFO notices |
| 5 | Playwright on desktop and phone, keyboard path | ✅ 10/10 locally, 4/4 @smoke on production |
| 6 | Lighthouse: accessibility ≥ 95, performance ≥ 90 | ✅ mobile 99 / 100 / 100 / 100, desktop 100 / 98→100 (perf / a11y / best practices / SEO) after adding a `<main>` landmark |
| 7 | Supabase stays awake | ⏳ daily `/api/health` cron registered (12:00 UTC); re-check on or after 2026-10-27 |

Notes from the deploy:

- **Same region pays off:** the database round trip is 3–6 ms from Vercel (`iad1`) against ~89 ms from the laptop.
- Vercel services take the Python entrypoint as a **file path** relative to the service root
  (`src/safescale/api/app.py`), and don't accept `excludeFiles`; `.vercelignore` keeps tests,
  environments, data and `.env` out of the 736 KB upload.
- Preview deployments are behind Vercel authentication (tested with `vercel curl`); production is public.
- Secrets were piped from `.env` into Vercel as hidden "Secret" variables, never printed.
- Latency measurement script: `evaluation/app_latency/measure.mjs` (raw numbers in `results.json`).

## Update (2026-10-20): landing page and routes

The site now opens on a landing page, and the tool has its own route:

| Route | What it is |
|---|---|
| `/` | Landing page. Hero: the brief's night-light description beside its **real** production result (hazard profile with baseline ticks, top evidence card verbatim), then the problem, how it works (4 sequential steps), what a signal does and doesn't tell you, how it's measured, and a closing form |
| `/analyze` | The tool (was `/`). `?q=…` prefills the description (read in the browser with `useSyncExternalStore`, so the page stays static); the landing examples and form use it. Loading shows a results skeleton |
| `/about` | Methodology (renamed in the nav) |

- The fixed disclaimer bar stays on `/analyze`, where results appear; other pages carry it in the
  site footer.
- New logo mark and favicon: a profile bar with its baseline tick.
- Numbers on the landing page come from a production run and are computed the same way as in the
  app (multiples from the real hazard counts), so the two always agree.
- Playwright: 12 tests (landing, landing form → tool, methodology, plus the tool tests) pass.
