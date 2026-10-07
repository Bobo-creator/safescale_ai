# Spec: retrieval

Module id: `retrieval` (see [CAPABILITY_MAP.md](CAPABILITY_MAP.md)). Depends on: `data-ingest`.
Consumed by: `hazard-analysis`, `explain`, `app`, `evaluation`.

## Objective

Given a free-text product description, return the top-k most similar historical recalls, each
with a rank and a score. Three methods share one interface so they can be compared:

| Method | How it ranks | Role |
|---|---|---|
| `vector` | Cosine similarity between OpenAI embeddings (pgvector k-NN) | Primary method |
| `keyword` | Postgres full-text search, any-term match, ranked by `ts_rank_cd` | Keyword baseline + hybrid input |
| `hybrid` | Reciprocal Rank Fusion (RRF) of the vector and keyword rankings | Brief's "nice-to-have"; cheap once both exist |

**Done looks like:** `safescale search "rechargeable children's night light, 2000 mAh lithium-ion battery, USB-C"`
prints the top matching recalls, with titles and links, from Supabase, for any of the three methods.

## Key facts (verified 2026-10-07)

- **OpenAI embeddings API:** `text-embedding-3-small` returns 1536 dimensions. Per request: at most
  8,192 tokens per input, 300,000 tokens in total, 2,048 inputs.
- **Our corpus:** 10,039 documents, 12.0 M characters (≈ 3 M tokens), longest 10,796 characters
  (≈ 2.7 k tokens, under the per-input limit, so nothing needs truncating). Embedding everything
  once should cost a few cents (confirm current price on OpenAI's pricing page before running).
- **pgvector:** 0.8.2 available on Supabase (not yet enabled), 0.8.7 locally. Both support HNSW
  indexes with `vector_cosine_ops`. pgvector's docs recommend RRF for hybrid search.
- **Pitfall avoided:** `plainto_tsquery` and `websearch_to_tsquery` AND every term together, so a
  15-word product description would almost never match anything. Keyword search therefore ORs
  the query's stemmed terms and lets ranking sort it out.

## Design

### Storage (migration `db/migrations/002_retrieval.sql`)

```sql
create extension if not exists vector;   -- no-op on Supabase once enabled by an admin (see Setup)

-- Embeddings live in their own table so re-ingesting recalls never touches them, and the
-- (model, content_hash) pair says exactly when a row must be re-embedded.
create table recall_embeddings (
  recall_id    bigint primary key references recalls (recall_id) on delete cascade,
  model        text not null,             -- e.g. 'text-embedding-3-small'
  content_hash text not null,             -- recalls.content_hash at embedding time
  embedding    vector(1536) not null,
  embedded_at  timestamptz not null default now()
);
create index recall_embeddings_hnsw on recall_embeddings
  using hnsw (embedding vector_cosine_ops);

-- Keyword search over the same canonical document.
alter table recalls
  add column search_tsv tsvector generated always as (to_tsvector('english', document)) stored;
create index recalls_search_tsv on recalls using gin (search_tsv);

alter table recall_embeddings enable row level security;
```

### Search as Postgres functions

Each method is a SQL function, so the Python pipeline, a FastAPI service and a Next.js route
can all call the same logic (Supabase can expose them as RPC later). Functions are
`security invoker`, so RLS still applies to whoever calls them.

```sql
search_recalls_vector(query_embedding vector(1536), k int)            -> (recall_id, rank, score)
search_recalls_keyword(query text, k int)                             -> (recall_id, rank, score)
search_recalls_hybrid(query text, query_embedding vector(1536), k int,
                      candidates int default 100, rrf_k int default 60) -> (recall_id, rank, score)
```

- **vector:** `order by embedding <=> query_embedding limit k`; score = `1 - cosine distance`.
- **keyword:** the query's lexemes from `to_tsvector('english', query)` joined with `|`;
  score = `ts_rank_cd`.
- **hybrid:** take the top `candidates` from each, score = Σ `1 / (rrf_k + rank)`, return top k.

### Python interface

```python
class Embedder(Protocol):
    model: str
    dimensions: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...

@dataclass(frozen=True)
class Hit:
    recall_id: int
    rank: int          # 1-based
    score: float       # method-specific; only comparable within one method
    title: str
    url: str

def search(conn, query: str, *, k: int = 25,
           method: Literal["vector", "keyword", "hybrid"] = "vector",
           embedder: Embedder | None = None) -> list[Hit]: ...
```

- `OpenAIEmbedder` wraps the official `openai` SDK (its built-in retries handle rate limits).
- `FakeEmbedder` (tests only): a deterministic bag-of-words hash into 1536 dimensions, so vector
  search can be tested offline with meaningful results.

### Embedding job

`safescale embed` finds recalls with no embedding, or whose `content_hash` or `model` differs
from the stored one, embeds them in batches (≤ 256 texts and ≤ 250 k estimated tokens per
request), and upserts the vectors. It logs the batches, total tokens used (from the API's
`usage`) and the number of rows embedded. It is safe to interrupt and re-run: each batch commits
on its own.

## Tech stack additions

- `openai` (official SDK), `pgvector` (Python adapter that registers the `vector` type with psycopg).
- `OPENAI_API_KEY` in `.env` (git-ignored); `EMBEDDING_MODEL` defaults to `text-embedding-3-small`.

## Commands

```bash
uv run safescale migrate                                   # applies 002_retrieval.sql
uv run safescale embed                                     # embed new/changed recalls
uv run safescale embed --limit 200                         # small trial run
uv run safescale search "lithium battery night light" --k 10 --method hybrid
uv run pytest                                              # offline; no OpenAI calls
uv run pytest -m live                                      # optional: one real OpenAI call
```

## Setup (one-time, Supabase)

The pipeline role is deliberately not an admin, so an admin step enables pgvector and lets the
role see it (I can run this through the Supabase plugin):

```sql
create extension if not exists vector with schema extensions;
grant usage on schema extensions to safescale_pipeline;
alter role safescale_pipeline set search_path = public, extensions;
```

## Project structure

```
db/migrations/002_retrieval.sql
pipeline/src/safescale/retrieval/
  embedder.py        # Embedder protocol, OpenAIEmbedder, batching by token budget
  index.py           # `embed` job: find stale rows, embed, upsert
  search.py          # search() → calls the SQL functions, returns Hits
pipeline/tests/retrieval/
  fake_embedder.py
  test_embedder.py   # batching, token budget, mocked OpenAI client
  test_index.py      # only stale rows embedded; re-run embeds 0
  test_search.py     # all three methods against fixture recalls on local Postgres
```

## Testing strategy

- **Unit:** batching respects both limits; a mocked OpenAI client verifies the request shape and
  that results come back in input order.
- **Integration (local Postgres + `FakeEmbedder`):** load the 18 fixture recalls, embed them,
  then check that a lithium-battery query ranks the lithium-ion fire recall (RecallID 166) first
  for vector, keyword and hybrid; that `k` is respected; that long queries still get keyword
  hits; and that changing one recall's document re-embeds only that row.
- **Live (opt-in, `-m live`):** one real embedding call to confirm the key, model and dimensions.
- Retrieval *quality* (Precision@K, NDCG@K, and so on) belongs to the `evaluation` module, not here.

## Boundaries

- **Always:** send OpenAI only recall documents and user queries; log token usage per run;
  keep tests offline by default.
- **Ask first:** changing the embedding model or dimensions (requires re-embedding everything and
  a new migration); running a full re-embed on Supabase after the first one.
- **Never:** commit the API key; embed per-request inside a loop of single calls; silently
  truncate documents.

## Success criteria

1. `safescale embed` on Supabase embeds all 10,039 recalls; an immediate re-run embeds 0.
2. After a recall's `content_hash` changes, the next `embed` re-embeds exactly that row.
3. `safescale search` returns exactly `k` hits for all three methods, each with rank, score,
   title and URL.
4. A long natural-language query (15+ words) returns keyword hits (no AND-everything failure).
5. Vector top-25 on Supabase uses the HNSW index and executes in < 50 ms in the database
   (`explain analyze`).
6. Sanity check on the brief's example (children's night light, 2000 mAh lithium-ion, USB-C, ABS
   housing, LED): at least 5 of the vector top 10 involve batteries, charging, overheating or fire.
   This is a manual check; the formal benchmark is in `evaluation`.
7. Tests and lint pass with no network access.

## Open questions

1. **OpenAI API key:** you'll need to create one (platform.openai.com → API keys) and add
   `OPENAI_API_KEY=...` to `.env` yourself, so it never passes through this chat. A small
   prepaid credit ($5) is more than enough.
2. **The "BM25" baseline:** Postgres `ts_rank_cd` is a keyword ranker but not true BM25 (it
   ignores how rare a term is across the corpus). My recommendation: keep Postgres full-text
   search for the live app and hybrid, and have `evaluation` also run a true BM25 (Python
   `bm25s`, offline) so the seminar's baseline is exactly what it claims to be.
3. **HNSW vs exact search:** at 10k rows exact search is also fast. We'll keep HNSW and let
   `evaluation` measure the latency difference, which the brief asks for anyway.
