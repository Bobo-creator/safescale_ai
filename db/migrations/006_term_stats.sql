-- hazard-analysis: corpus document frequencies of full-text lexemes, for ranking the terms a
-- report shows (shared with the description, and recurring failure terms in hazard text).
-- Refreshed by `safescale classify`. Table names inside ts_stat are schema-qualified because
-- Postgres 17 builds and refreshes materialized views with a restricted search_path.

create materialized view recall_term_df as
  select word as lexeme, ndoc from ts_stat('select search_tsv from public.recalls');

create unique index recall_term_df_lexeme on recall_term_df (lexeme);

create materialized view recall_hazard_term_df as
  select word as lexeme, ndoc
  from ts_stat($q$select to_tsvector('english', hazard_text) from public.recalls
                  where hazard_text is not null$q$);

create unique index recall_hazard_term_df_lexeme on recall_hazard_term_df (lexeme);

-- Materialized views can't use row-level security; keep them out of Supabase's Data API instead.
do $$
declare r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on recall_term_df, recall_hazard_term_df from %I', r);
    end if;
  end loop;
end
$$;
