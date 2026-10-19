# Tasks: hazard-taxonomy

Plan: [plan.md](plan.md) · Spec: [SPEC-hazard-taxonomy.md](../SPEC-hazard-taxonomy.md)

### Task 1: Gold sample + labeling page (`safescale label`)
**Acceptance:**
- [x] Seeded sample of 50 recall ids is deterministic and written to `evaluation/hazard_gold/gold.json` with empty labels
- [x] Page shows title, hazard text, description, CPSC link; 12 category checkboxes + "violates a standard" + notes; never shows predictions
- [x] Each change saves immediately; reload resumes; progress + jump-to-unlabeled; server binds to 127.0.0.1
**Verify:** `uv run pytest tests/taxonomy/test_labeling.py`; Playwright check of render/save/resume
**Files:** `taxonomy/categories.py`, `taxonomy/labeling/`, `cli.py`, tests · **Scope:** M

### Task 2: Hazard rules + `classify()`
**Acceptance:**
- [ ] ~60 table-driven phrases pass, including the traps ("lead to", "fall out of position", "injury hazard", one-word records, multi-hazard)
- [ ] Field order hazard+title → description fallback → `other`; evidence is a verbatim fragment ≤ 160 chars
**Verify:** `uv run pytest tests/taxonomy/test_rules.py tests/taxonomy/test_classify.py`
**Files:** `taxonomy/rules.py`, `taxonomy/classify.py`, tests · **Scope:** M

### Task 3: Standards-violation rules
**Acceptance:**
- [ ] Trigger + named standard (ASTM F…, 16 CFR …, named federal standards) extracted; trigger without a name gives `standard=None`
**Verify:** `uv run pytest tests/taxonomy/test_classify.py`
**Files:** `taxonomy/rules.py`, `taxonomy/classify.py`, tests · **Scope:** S

### Checkpoint: classifier
- [ ] All tests + lint pass; on the full local corpus (gold ids excluded): `other`-only ≤ 10%, ≥ 1,000 violation flags, ≥ half named

### Task 4: Migration 004
**Acceptance:**
- [ ] `hazard_categories` (seeded), `recall_hazards`, `recall_standard_violations`, all with RLS
- [ ] Test: seed matches `categories.py`
**Verify:** `uv run pytest tests/test_db.py tests/taxonomy/test_store.py`
**Files:** `db/migrations/004_hazard_taxonomy.sql`, `tests/test_db.py` · **Scope:** S

### Task 5: `classify_all`, `labels_for`, `safescale classify` / `hazards`
**Acceptance:**
- [ ] Full recompute in one transaction; re-run gives identical rows; per-category counts printed
- [ ] `labels_for` returns 25 ids in one query; `hazards 166` prints `fire_overheating` with evidence
**Verify:** `uv run pytest tests/taxonomy/test_store.py`; manual CLI run locally
**Files:** `taxonomy/store.py`, `cli.py`, tests · **Scope:** M

### Task 6: Supabase run
**Acceptance:**
- [ ] 004 applied by the pipeline role; classify < 10 s; re-run identical; advisors: no new warnings
**Verify:** SQL counts, timings, advisors · **Scope:** S

### Task 7: `safescale score-hazards` (after your labels are in)
**Acceptance:**
- [ ] Per-category + micro P / R / F1 with raw counts, plus violation-flag P / R
- [ ] Result recorded in the spec; target micro-F1 ≥ 0.85
**Verify:** `uv run pytest tests/taxonomy/test_score.py`; run on `gold.json`
**Files:** `taxonomy/score.py`, `cli.py`, tests · **Scope:** S

### Checkpoint: hazard-taxonomy complete
- [ ] Spec success criteria 1–8 met; README updated; committed to main
