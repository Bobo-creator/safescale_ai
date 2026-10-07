# Implementation Plan: data-ingest

Implements [SPEC-data-ingest.md](../SPEC-data-ingest.md). Tasks are in [todo.md](todo.md).

## Overview

A Python CLI (`safescale`) that downloads all CPSC recalls, cleans them, and upserts them into
Postgres (`recalls` + `ingest_runs`). We build and test locally first, then point the same command
at Supabase.

## Architecture decisions

- **Local Postgres via Homebrew, not Docker.** Docker isn't installed on this machine;
  `brew install postgresql@16 pgvector` is lighter and gives the same Postgres + pgvector
  versions as Supabase. (This changes the spec's `docker compose` line, which gets updated once
  you approve.)
- **`uv` for Python.** It isn't installed yet; `brew install uv`.
- **Migrations are plain SQL with a tiny runner** that records applied files in a
  `schema_migrations` table. The same files are applied to Supabase, so there is no ORM and no
  framework lock-in.
- **Two different hashes:**
  - `content_hash = sha256(document)` tells `retrieval` when to re-embed.
  - Update detection compares the stored `raw` JSONB with the incoming record, so changes outside
    `document` (e.g. remedy text) are still picked up.
- **Upsert in one statement:** `INSERT … ON CONFLICT (recall_id) DO UPDATE … WHERE recalls.raw IS
  DISTINCT FROM EXCLUDED.raw RETURNING (xmax = 0)` gives inserted/updated counts; unchanged =
  fetched − inserted − updated − rejected.
- **HTTP mocked with `httpx.MockTransport`.** Tests never hit the network and need no extra
  mocking library.
- **Pure core, side effects at the edges:** `clean.py` and `document.py` are pure and
  unit-tested; `fetch.py` and `load.py` do the I/O.

## Dependency graph

```
scaffold (1) ──► migrations (2) ──────────────┐
      │                                       ▼
      └──► fixtures (3) ──► models+clean (4) ──► document (5) ──► load (6) ──► fetch+CLI (7) ──► Supabase (8)
```

## Phases

1. **Foundation (tasks 1–3):** project skeleton, local DB and migrations, real test fixtures.
2. **Core (tasks 4–7):** parse → clean → document → load → fetch, finishing with a full local
   ingest of about 10k rows.
3. **Production DB (task 8):** run the same pipeline against Supabase.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| CPSC API changes shape or goes down | Med | Pydantic validation counts rejects; `--snapshot` loads from a saved file; by-year fetch as fallback |
| Messy text (HTML entities, odd placeholders) | Med | Fixtures chosen for edge cases; `clean.py` fully unit-tested |
| Upsert counts wrong | Med | Integration tests for fresh, re-run and changed-record cases |
| Supabase connection limits / pooler quirks | Low | Ingest uses one connection and one transaction; use the session pooler URL |
| Snapshot or `.env` accidentally committed | Med | `.gitignore` set up in task 1 before any data exists |

## Open questions

- None blocking. Supabase project creation (task 8) is outward-facing, so I'll confirm the
  project name and region with you before creating it.
