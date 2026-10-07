# Tasks: data-ingest

Plan: [plan.md](plan.md) · Spec: [SPEC-data-ingest.md](../SPEC-data-ingest.md)

## Phase 1: Foundation

### Task 1: Project scaffold and tooling
**Description:** Install `uv`; create the `pipeline/` package with a `safescale` CLI entry point,
ruff and pytest configured; add `.gitignore` (data/raw, .env, venvs) and `.env.example`.
**Acceptance:**
- [x] `uv run safescale --help` lists `migrate` and `ingest`
- [x] `uv run pytest` runs (a smoke test passes); `uv run ruff check .` is clean
- [x] `data/raw/` and `.env` are git-ignored
**Verify:** run the three commands above; `git check-ignore data/raw/x.json .env`
**Dependencies:** None
**Files:** `pipeline/pyproject.toml`, `pipeline/src/safescale/cli.py`, `pipeline/tests/test_smoke.py`, `.gitignore`, `.env.example`
**Scope:** S

### Task 2: Local Postgres, migration 001 and runner
**Description:** Install Postgres 16 + pgvector via Homebrew and create the `safescale` database.
Write `db/migrations/001_recalls.sql` (from the spec) and `db.py` with a runner that applies
pending files in order and records them in `schema_migrations`.
**Acceptance:**
- [x] `uv run safescale migrate` creates `recalls`, `ingest_runs`, `schema_migrations`
- [x] Running it again applies nothing and exits 0
- [x] Integration test proves both behaviours on a throwaway test database
**Verify:** `uv run pytest tests/test_db.py`; `psql safescale -c '\dt'`
**Dependencies:** 1
**Files:** `db/migrations/001_recalls.sql`, `pipeline/src/safescale/db.py`, `pipeline/src/safescale/cli.py`, `pipeline/tests/conftest.py`, `pipeline/tests/test_db.py`
**Scope:** M

### Task 3: Real-record test fixtures
**Description:** Pull about 20 real records from a CPSC snapshot into `tests/fixtures/recalls_sample.json`,
chosen for edge cases: no hazards, no description, HTML entities, multiple products, a 1970s
record, a recent record with empty `Products[].Type`.
**Acceptance:**
- [x] Fixture file exists, is valid JSON, and covers every edge case listed (noted in a README beside it)
**Verify:** `python -m json.tool` on the file; manual review of the edge-case list
**Dependencies:** 1
**Files:** `pipeline/tests/fixtures/recalls_sample.json`, `pipeline/tests/fixtures/README.md`
**Scope:** XS

### Checkpoint: Foundation
- [x] Tests and lint pass
- [x] `safescale migrate` works on the local DB

## Phase 2: Core pipeline

### Task 4: Pydantic models and cleaning
**Description:** `models.py` validates raw CPSC records; `clean.py` holds pure functions (HTML
unescape/strip, whitespace, placeholders → None, list dedupe, date parsing) and maps a raw record
to a cleaned `RecallRow`.
**Acceptance:**
- [x] All fixture records parse; a deliberately malformed record raises a validation error naming the field
- [x] Unit tests cover each cleaning rule and each fixture edge case
**Verify:** `uv run pytest tests/ingest/test_clean.py`
**Dependencies:** 3
**Files:** `ingest/models.py`, `ingest/clean.py`, `tests/ingest/test_clean.py`
**Scope:** M

### Task 5: Canonical document and content hash
**Description:** `document.py` builds the `Title / Products / Hazard / Description / Injuries` text,
omitting empty sections, and computes `content_hash`.
**Acceptance:**
- [x] Every fixture produces a non-empty document; empty sections are omitted
- [x] The same input always produces the same hash (deterministic order and formatting)
**Verify:** `uv run pytest tests/ingest/test_document.py`
**Dependencies:** 4
**Files:** `ingest/document.py`, `tests/ingest/test_document.py`
**Scope:** S

### Task 6: Load (upsert) and ingest_runs
**Description:** `load.py` upserts cleaned rows in one transaction, returns
inserted/updated/unchanged/rejected counts, and writes an `ingest_runs` row.
**Acceptance:**
- [x] Fresh load: inserted = N, updated = 0
- [x] Immediate re-load: inserted = 0, updated = 0
- [x] Changing one record's raw content: updated = 1, and `updated_at` moves for that row only
**Verify:** `uv run pytest tests/ingest/test_load.py`
**Dependencies:** 2, 5
**Files:** `ingest/load.py`, `tests/ingest/test_load.py`
**Scope:** M

### Task 7: Fetch, snapshot and the `ingest` command
**Description:** `fetch.py` downloads the full dataset, writes `data/raw/recalls_<ts>.json` and its
SHA-256. Wire `safescale ingest [--snapshot PATH] [--limit N]` end to end, logging every rejected
record with its RecallID and reason.
**Acceptance:**
- [x] Mocked-HTTP test: fetch writes a snapshot and returns the correct hash
- [x] `--snapshot` makes no network call; `--limit 500` loads exactly 500 rows
- [x] Real run against local DB: ≥ 10,000 rows in < 2 min; re-run reports 0 inserted / 0 updated
**Verify:** `uv run pytest`; `time uv run safescale ingest`; run it twice; SQL spot-checks for the spec's success criteria 3–6
**Dependencies:** 6
**Files:** `ingest/fetch.py`, `ingest/__init__.py` (pipeline orchestration), `cli.py`, `tests/ingest/test_fetch.py`
**Scope:** M

### Checkpoint: Core (spec success criteria 1–7, locally)
- [x] All tests and lint pass
- [x] Full local ingest meets every success criterion in the spec
- [x] Review with you before touching Supabase

## Phase 3: Production database

### Task 8: Run against Supabase
**Description:** Create or link a Supabase project (**confirm name and region with you first**),
put the connection string in `.env`, run `safescale migrate` and `safescale ingest` against it,
then check the Supabase security advisors.
**Acceptance:**
- [ ] Supabase has ≥ 10,000 rows in `recalls` and one `ingest_runs` row
- [ ] RLS is enabled on the new tables (no public read/write through the Data API until `app` decides access)
- [ ] No critical security advisor warnings
**Verify:** row count via SQL; Supabase advisors
**Dependencies:** 7
**Files:** `.env` (local only), possibly `db/migrations/002_rls.sql`
**Scope:** S

### Checkpoint: data-ingest complete
- [ ] Spec success criteria met on Supabase
- [ ] README status updated; commit
