# Tasks: hazard-analysis

Plan: [plan.md](plan.md) · Spec: [SPEC-hazard-analysis.md](../SPEC-hazard-analysis.md)

### Task 1: Report model, hazard profile and signals (pure)
**Acceptance:**
- [x] Profile per category: count, share, base rate, lift, recall ids; only relevant matches counted
- [x] Signal rule at every threshold edge; `other` never drives the overall signal; < 5 relevant → insufficient evidence
- [x] `to_dict()` is JSON-ready and always includes the disclaimer
**Verify:** `uv run pytest tests/analysis/test_profile.py`
**Files:** `analysis/report.py`, `analysis/profile.py`, tests · **Scope:** M

### Task 2: Matches for any method (cosine + labels)
**Acceptance:**
- [x] Each hit gets its cosine from stored embeddings (also for keyword/hybrid), labels and violations; weak matches flagged
**Verify:** `uv run pytest tests/analysis/test_analyze.py -k matches`
**Files:** `analysis/analyze.py`, tests · **Scope:** S

### Task 3: Term statistics + shared / failure terms
**Acceptance:**
- [x] Migration 006: two materialized views, Data API roles revoked; refreshed by `classify`
- [x] Shared terms (≥ 2 matches) and failure terms (≥ 3 matches, not in query) ranked by share × idf, shown as surface words
**Verify:** `uv run pytest tests/analysis/test_terms.py tests/test_db.py`
**Files:** `db/migrations/006_term_stats.sql`, `analysis/terms.py`, `taxonomy/store.py`, tests · **Scope:** M

### Task 4: Investigation catalog
**Acceptance:**
- [x] ~20 entries; an area shows only with ≥ 2 supporting matches, with recall ids and trigger terms
- [x] Standards named by ≥ 2 matches listed; wording test passes on every catalog string
**Verify:** `uv run pytest tests/analysis/test_investigate.py`
**Files:** `analysis/investigate.py`, tests · **Scope:** M

### Checkpoint: offline
- [x] All tests + lint pass with no network

### Task 5: `analyze()` and `safescale analyze [--json]`
**Acceptance:**
- [x] End to end with FakeEmbedder on fixtures; every recall id in the report is a relevant match; JSON round-trips
**Verify:** `uv run pytest tests/analysis/test_analyze.py`
**Files:** `analysis/analyze.py`, `cli.py`, tests · **Scope:** M

### Task 6: Supabase sanity run
**Acceptance:**
- [x] 006 applied; night light, dresser and unrelated queries meet spec criteria 2–4; k = 25/50/100 × 3 methods work
- [x] DB work < 300 ms warm (~58 ms server-side; ~410 ms incl. 8 laptop round trips), CLI 2.1–2.6 s from the laptop (re-measure in `app`); advisors: no new warnings; results recorded in the spec
**Verify:** CLI runs, timings, advisors · **Scope:** S

### Checkpoint: hazard-analysis complete
- [x] Spec success criteria 1–7 met; README updated; committed to main
