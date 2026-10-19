# Implementation Plan: hazard-analysis

Implements [SPEC-hazard-analysis.md](../../SPEC-hazard-analysis.md). Tasks: [hazard-analysis-todo.md](hazard-analysis-todo.md).
Previous modules: [data-ingest](data-ingest-plan.md), [retrieval](retrieval-plan.md),
[hazard-taxonomy](hazard-taxonomy-plan.md).

## Overview

A deterministic report builder: retrieval hits + stored hazard labels + term statistics →
`HazardReport` (profile with lift, LOW/MODERATE/HIGH signals, shared/failure terms, investigation
areas, cited standards, disclaimer), exposed as `analyze()` and `safescale analyze [--json]`.

## Approved decisions (2026-10-19)

- k = 25 default; relevance floor 0.30 (cosine); signal rule v1 frozen before evaluation.
- Investigation catalog drafted by me, reviewed by the owner in real reports.
- No LLM in this module; every statement carries recall ids; disclaimer on every report.

## Order and why

The pure core (profile + signals) comes first: it is the heart of the module and fully testable
without a database. Then cosine-for-any-method and labels, then terms (needs a migration), then the
catalog, then the CLI and the Supabase sanity run against the spec's expected outcomes.

## Dependency graph

```
report dataclasses + profile/signals (1) ──┐
matches: cosine for any method + labels (2) ┼─► analyze() + CLI (5) ─► Supabase sanity (6)
term stats migration + terms (3) ───────────┤
investigation catalog (4) ──────────────────┘
```

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Report reads as a risk prediction | High | Lift next to every share, fixed disclaimer, wording tests (no "safe"/"compliant"/"certified") |
| Thresholds tuned to the 4 prototype queries | Med | Frozen as constants now; `evaluation` tests them on held-out recalls |
| Materialized views exposed through Supabase's Data API (no RLS on views) | Med | Revoke from `anon`/`authenticated` in the migration; test + advisors check |
| Stemmed lexemes shown to users ("batteri") | Low | Map each lexeme back to its most common surface word |
| Hybrid/keyword scores aren't cosine | Low | Fetch each hit's cosine from stored embeddings; floor always on cosine |
