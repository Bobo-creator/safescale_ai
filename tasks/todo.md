# Tasks: explain

Plan: [plan.md](plan.md) · Spec: [SPEC-explain.md](../SPEC-explain.md)

### Task 1: Output schema + grounding validator
**Acceptance:**
- [x] Pydantic schema per spec (citations min 1, category enum, size limits)
- [x] Catches: unknown id, wrong-category / wrong-area citation, invented number, banned word, unknown area, empty summary; each with a readable reason
**Verify:** `uv run pytest tests/explain/test_validate.py`
**Files:** `explain/schema.py`, `explain/validate.py`, tests · **Scope:** M

### Task 2: Evidence packet
**Acceptance:**
- [x] Only relevant matches, top 15 by rank; product names + truncated hazard/description text; ids all from the report
**Verify:** `uv run pytest tests/explain/test_packet.py`
**Files:** `explain/packet.py`, tests · **Scope:** S

### Task 3: explain() flow (FakeExplainer)
**Acceptance:**
- [x] Valid first try; retry with feedback; fallback template; insufficient evidence → no model call
- [x] Explanation carries caveat, disclaimer, validation record, usage; `to_dict()` JSON-ready
**Verify:** `uv run pytest tests/explain/test_explain.py`
**Files:** `explain/explain.py`, `explain/prompt.py`, `tests/fake_explainer.py`, tests · **Scope:** M

### Checkpoint: offline
- [x] All tests + lint pass with no network

### Task 4: OpenAIExplainer + live test
**Acceptance:**
- [x] `responses.parse` with the schema; usage (input/output/reasoning tokens) and cost estimate recorded
- [x] `-m live`: night-light explanation passes validation
**Verify:** `uv run pytest -m live tests/explain`
**Files:** `explain/explainer.py`, `tests/explain/test_explainer.py`, `tests/explain/test_live.py` · **Scope:** S

### Task 5: `safescale explain [--json] [--model]`
**Acceptance:**
- [ ] Text with [#id] citations + numbered references + caveat + disclaimer; JSON = report + explanation
**Verify:** CLI test with fakes; manual run on Supabase
**Files:** `explain/text.py`, `cli.py`, tests · **Scope:** S

### Task 6: Benchmark + review sheet
**Acceptance:**
- [ ] 10 queries × {gpt-6-luna, gpt-6.1-sol}: first-try pass rate, drops, retries, fallback, latency, cost recorded in the spec
- [ ] `evaluation/explain_review/` sheet with 5 luna explanations for the owner
**Verify:** benchmark run; owner review (target ≥ 95% supported) · **Scope:** M

### Checkpoint: explain complete
- [ ] Spec success criteria 1–7 met; README updated; committed to main
