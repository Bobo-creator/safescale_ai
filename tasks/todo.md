# Tasks: app

Plan: [plan.md](plan.md) · Spec: [SPEC-app.md](../SPEC-app.md)

### Task 1: Migration 007 (app role policies, rate-limit table) + limits
**Acceptance:**
- [x] RLS select policies for `safescale_app` on the read tables; `app_rate_limits(bucket, window_start, count)`; grants
- [x] `limits.py`: atomic increment per (salted-IP bucket, hour) and global daily explanation cap; env-configurable
- [x] Test: app role can read what analysis needs, cannot write recalls or run DDL; anon still locked out
**Verify:** `uv run pytest tests/api/test_limits.py tests/test_db.py`
**Files:** `db/migrations/007_app_access.sql`, `api/limits.py`, tests · **Scope:** M

### Task 2: FastAPI app
**Acceptance:**
- [ ] `/api/analyze`, `/api/explain`, `/api/examples`, `/api/health`; input validation (422); 429 with retry-after; daily cap skips explanation only
- [ ] OpenAI failure → report + fallback summary; DB failure → 503 without stack traces; request bodies never logged
**Verify:** `uv run pytest tests/api`
**Files:** `api/app.py`, `api/deps.py`, `pyproject.toml`, tests · **Scope:** M

### Checkpoint: back end
- [ ] All tests + lint pass offline; `uvicorn` against Supabase answers the night-light query

### Task 3: Next.js scaffold + typed API client
**Acceptance:**
- [ ] `web/` (App Router, TypeScript strict, Tailwind); dev proxy `/api` → :8000; types mirror the API JSON
- [ ] Minimal page runs the night-light query end to end locally
**Verify:** `npm run lint && npm run build`; manual run
**Files:** `web/**` · **Scope:** M

### Task 4: Dashboard UI (frontend-design)
**Acceptance:**
- [ ] Input panel (examples, k, Advanced method), signal, profile chart with lift, terms, areas, standards, evidence cards, explanation with citation → card jump, disclaimer + caveat always visible
- [ ] Loading, error, 429 and insufficient-evidence states; light/dark; phone width; keyboard reachable; `/about` page
**Verify:** build + manual review in the browser (Playwright screenshots)
**Files:** `web/app/**`, `web/components/**` · **Scope:** L (split into sub-steps while building)

### Task 5: Playwright e2e (local)
**Acceptance:**
- [ ] Night-light flow, citation jump, k/method switch, unrelated-query notice, phone layout, keyboard path
**Verify:** `npx playwright test`
**Files:** `e2e/**`, `playwright.config.ts` · **Scope:** S

### Checkpoint: local
- [ ] Full flow works locally against Supabase; all tests pass

### Task 6: `safescale_app` role on Supabase (outward-facing)
**Acceptance:**
- [ ] Role created with a locally generated password (verifier only sent to Supabase; plaintext in `.env`); 007 applied; access test passes against Supabase; advisors clean
**Verify:** connection test as the app role via the transaction pooler · **Scope:** S

### Task 7: Vercel deploy + verification (outward-facing)
**Acceptance:**
- [ ] `vercel.json` services/rewrites/cron/region; env vars set; preview deploy → e2e green → production
- [ ] Speed (median of 10 from the browser): analysis < 2 s, explanation < 12 s; Lighthouse a11y ≥ 95, perf ≥ 90; results in the spec
**Verify:** e2e against the deployment, timing script, Lighthouse · **Scope:** M

### Checkpoint: app complete
- [ ] Spec success criteria 1–6 met; criterion 7 (keep-alive) re-checked a week later; README updated; committed to main
