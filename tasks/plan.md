# Implementation Plan: app

Implements [SPEC-app.md](../SPEC-app.md). Tasks: [todo.md](todo.md).
Previous modules: [data-ingest](done/data-ingest-plan.md), [retrieval](done/retrieval-plan.md),
[hazard-taxonomy](done/hazard-taxonomy-plan.md), [hazard-analysis](done/hazard-analysis-plan.md),
[explain](done/explain-plan.md).

## Overview

FastAPI inside the `safescale` package (`/api/analyze`, `/api/explain`, `/api/examples`,
`/api/health`) with rate limits and a least-privilege DB role, plus a Next.js dashboard in `web/`,
deployed as one Vercel project (services + rewrites, region iad1, daily keep-alive cron).

## Approved decisions (2026-10-19)

- Same OpenAI key as the pipeline; spend guarded by 300 explanations/day + per-visitor limits.
- Limits 30 analyses / 10 explanations per visitor-hour; method selector under "Advanced".
- No streaming in v1 (only validated text is shown); no storage of descriptions.

## Order and why

Back end first, tested offline (it holds the security-relevant parts: limits, DB role, input
validation). Then the UI against the local API on Supabase, then e2e, then the two outward-facing
steps (Supabase role, Vercel project) once everything works locally.

## Dependency graph

```
migration 007 + limits (1) ─► FastAPI app (2) ─┬─► Next.js scaffold + API client (3) ─► UI design (4) ─► e2e (5)
                                               └───────────────────────────────────────────────────────────┐
                                     safescale_app role on Supabase (6) ─► Vercel deploy + verify (7) ◄─────┘
```

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Public endpoint drains the OpenAI key | High | Daily explanation cap + per-visitor limits, enforced in the DB before any paid call |
| Transaction pooler + prepared statements break psycopg | Med | `prepare_threshold=None`; tested against the pooler before deploy |
| Python bundle or build fails on Vercel services | Med | Deploy a preview early in Task 7; keep `excludeFiles` for tests/fixtures |
| Cold starts (Vercel function + Supabase) exceed 2 s | Med | Measure warm vs cold separately; keep-alive cron; report honestly |
| Descriptions leak into logs | Med | Never log bodies; test asserts it; no analytics |
