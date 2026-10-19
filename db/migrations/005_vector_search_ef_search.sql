-- Fix: HNSW returns at most hnsw.ef_search rows (default 40), so vector search silently capped k
-- at 40 and hybrid only ever saw 40 vector candidates out of the 100 it asked for. Raise
-- ef_search to k for the current transaction before searching (capped at 1000).
-- volatile, not stable: the function now changes a setting (transaction-local).

create or replace function search_recalls_vector(query_embedding vector(1536), k int)
returns table (recall_id bigint, rank bigint, score double precision)
language plpgsql volatile security invoker
set search_path = public, extensions
as $$
begin
  perform set_config('hnsw.ef_search', least(greatest(k, 40), 1000)::text, true);
  return query execute
    'select s.recall_id,
            row_number() over (order by s.distance, s.recall_id),
            1 - s.distance
     from (
       select e.recall_id, e.embedding <=> $1 as distance
       from recall_embeddings e
       order by e.embedding <=> $1
       limit $2
     ) s
     order by 2'
  using query_embedding, k;
end
$$;

-- hybrid calls the vector function, so it can no longer be declared stable either.
alter function search_recalls_hybrid(text, vector, int, int, int) volatile;
