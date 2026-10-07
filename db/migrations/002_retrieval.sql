-- retrieval: embeddings (pgvector), keyword search (full-text), and search functions.
-- On Supabase, pgvector is enabled once by an admin in the `extensions` schema and the pipeline
-- role's search_path includes it, so the create below is a no-op there.

create extension if not exists vector;

-- Embeddings live in their own table so re-ingesting recalls never touches them; the
-- (model, content_hash) pair says exactly when a row must be re-embedded.
create table recall_embeddings (
  recall_id    bigint primary key references recalls (recall_id) on delete cascade,
  model        text not null,
  content_hash text not null,
  embedding    vector(1536) not null,
  embedded_at  timestamptz not null default now()
);

create index recall_embeddings_hnsw on recall_embeddings
  using hnsw (embedding vector_cosine_ops);

alter table recall_embeddings enable row level security;

-- Keyword search over the same canonical document used for embeddings.
alter table recalls
  add column search_tsv tsvector generated always as (to_tsvector('english', document)) stored;

create index recalls_search_tsv on recalls using gin (search_tsv);

-- Each search function returns (recall_id, rank, score) with rank 1..k. Scores are only
-- comparable within one method. security invoker keeps the caller's RLS in force.

create function search_recalls_vector(query_embedding vector(1536), k int)
returns table (recall_id bigint, rank bigint, score double precision)
language sql stable security invoker
set search_path = public, extensions
as $$
  select s.recall_id,
         row_number() over (order by s.distance, s.recall_id),
         1 - s.distance
  from (
    select e.recall_id, e.embedding <=> query_embedding as distance
    from recall_embeddings e
    order by e.embedding <=> query_embedding    -- this exact form lets HNSW serve the query
    limit k
  ) s
  order by 2
$$;

-- Matches documents containing ANY of the query's stemmed terms (plainto/websearch_to_tsquery
-- would require ALL of them, which a long product description almost never satisfies).
create function search_recalls_keyword(query text, k int)
returns table (recall_id bigint, rank bigint, score double precision)
language sql stable security invoker
set search_path = public, extensions
as $$
  with q as (
    select to_tsquery('simple', string_agg(quote_literal(t.lexeme), ' | ')) as tsq
    from unnest(to_tsvector('english', query)) as t
  )
  select s.recall_id, row_number() over (order by s.score desc, s.recall_id), s.score
  from (
    select r.recall_id, ts_rank_cd(r.search_tsv, q.tsq)::double precision as score
    from recalls r, q
    where r.search_tsv @@ q.tsq
    order by score desc, r.recall_id
    limit k
  ) s
  order by 2
$$;

-- Reciprocal Rank Fusion of the vector and keyword rankings.
create function search_recalls_hybrid(
  query text,
  query_embedding vector(1536),
  k int,
  candidates int default 100,
  rrf_k int default 60
)
returns table (recall_id bigint, rank bigint, score double precision)
language sql stable security invoker
set search_path = public, extensions
as $$
  select s.recall_id, row_number() over (order by s.score desc, s.recall_id), s.score
  from (
    select u.recall_id, sum(1.0 / (rrf_k + u.rank))::double precision as score
    from (
      select v.recall_id, v.rank from search_recalls_vector(query_embedding, candidates) v
      union all
      select w.recall_id, w.rank from search_recalls_keyword(query, candidates) w
    ) u
    group by u.recall_id
    order by score desc, u.recall_id
    limit k
  ) s
  order by 2
$$;
