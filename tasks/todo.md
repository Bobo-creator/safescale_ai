# Tasks: retrieval

Plan: [plan.md](plan.md) · Spec: [SPEC-retrieval.md](../SPEC-retrieval.md)

### Task 1: Migration 002 (embeddings table, tsvector, indexes, search functions)
**Acceptance:**
- [x] `safescale migrate` applies `002_retrieval.sql` locally; RLS on `recall_embeddings`
- [x] The three SQL functions exist; `search_recalls_keyword` returns hits for a long query and 0 rows for a stopword-only query
**Verify:** `uv run pytest tests/test_db.py tests/retrieval/test_search.py`
**Files:** `db/migrations/002_retrieval.sql`, tests · **Scope:** M

### Task 2: Embedder (OpenAI + fake) with token-budget batching
**Acceptance:**
- [x] Batches respect ≤ 256 texts and ≤ 250 k estimated tokens; output order matches input
- [x] Mocked OpenAI client: correct model, inputs and dimension check
**Verify:** `uv run pytest tests/retrieval/test_embedder.py`
**Files:** `retrieval/embedder.py`, `tests/retrieval/fake_embedder.py`, `tests/retrieval/test_embedder.py` · **Scope:** S

### Task 3: `search()` over the three SQL functions
**Acceptance:**
- [x] With the fake embedder on the fixtures, a lithium-battery fire query ranks RecallID 166 first for vector, keyword and hybrid
- [x] Exactly `k` hits (when enough rows exist), ranks 1..k, with title and URL
**Verify:** `uv run pytest tests/retrieval/test_search.py`
**Files:** `retrieval/search.py`, `tests/retrieval/test_search.py` · **Scope:** M

### Task 4: `safescale embed` job
**Acceptance:**
- [x] Embeds only missing/stale rows (content_hash or model changed); re-run embeds 0
- [x] Logs batches and total tokens; each batch commits independently; `--limit` works
**Verify:** `uv run pytest tests/retrieval/test_index.py`
**Files:** `retrieval/index.py`, `cli.py`, `tests/retrieval/test_index.py` · **Scope:** M

### Task 5: `safescale search` CLI
**Acceptance:**
- [x] Prints rank, score, date, title, URL for `--method vector|keyword|hybrid`, `--k`
**Verify:** CLI test with fake embedder; manual run
**Files:** `cli.py`, `tests/test_cli_search.py` · **Scope:** S

### Checkpoint: local
- [x] All tests + lint pass offline; one `-m live` OpenAI call succeeds

### Task 6: Supabase — admin setup, migrate, full embed, verify
**Acceptance:**
- [x] pgvector enabled, role granted; `002` applied by the pipeline role
- [x] 10,039 embeddings; re-run embeds 0; tokens/cost logged
- [x] Vector top-25 uses HNSW, < 50 ms DB execution; brief's night-light example sanity check (≥ 5/10 battery/charging/fire)
- [x] Security advisors: no new warnings
**Verify:** SQL counts, `explain analyze`, `safescale search`, advisors
**Scope:** S

### Checkpoint: retrieval complete
- [x] Spec success criteria 1–7 met; README updated; committed to main
