-- Fix: search_recalls_vector ignored the HNSW index.
-- A SQL function with a SET clause is not inlined, so its query is planned with k as an unknown
-- parameter; the generic plan then prefers a sequential scan + sort over all vectors (~65 ms on
-- Supabase vs ~1 ms through the index). Dynamic SQL is planned on each call with the real k.

create or replace function search_recalls_vector(query_embedding vector(1536), k int)
returns table (recall_id bigint, rank bigint, score double precision)
language plpgsql stable security invoker
set search_path = public, extensions
as $$
begin
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
