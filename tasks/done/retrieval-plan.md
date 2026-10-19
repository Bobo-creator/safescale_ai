# Implementation Plan: retrieval

Implements [SPEC-retrieval.md](../../SPEC-retrieval.md). Tasks: [retrieval-todo.md](retrieval-todo.md).
Previous module: [done/data-ingest-plan.md](data-ingest-plan.md).

## Overview

Add embeddings (OpenAI → pgvector), keyword search (Postgres FTS) and hybrid search (RRF) as SQL
functions, a Python `search()` wrapper, and `safescale embed` / `safescale search` commands.
Build and test locally with a fake embedder, then embed for real on Supabase.

## Approved decisions (2026-10-07)

- OpenAI `text-embedding-3-small` (1536 d); new deps `openai`, `pgvector`.
- Keyword = Postgres FTS (OR of stemmed terms, `ts_rank_cd`); true BM25 is added offline in `evaluation`.
- Supabase admin step via the plugin: enable pgvector in `extensions`, grant it to `safescale_pipeline`.
- HNSW index kept; `evaluation` measures exact vs HNSW latency.

## Dependency graph

```
migration 002 (1) ──► search functions + search() (3) ──► CLI search (5) ──┐
embedder (2) ──────► embed job (4) ──────────────────────────────────────┴─► Supabase run (6)
```

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `vector` type invisible to the pipeline role on Supabase (lives in `extensions`) | High | Admin step sets the role's `search_path`; migration checked on Supabase before embedding |
| OpenAI rate limits / transient errors mid-run | Med | SDK retries; each batch commits, so re-running resumes |
| Token estimate off, request over 300 k tokens | Low | Conservative chars/3 estimate with a 250 k budget; longest doc is ~2.7 k tokens |
| Keyword query with no usable terms (e.g. only stopwords) | Low | Function returns zero rows instead of erroring; tested |
| Generated `search_tsv` column rewrite on 10k rows | Low | One-off, a few seconds |
