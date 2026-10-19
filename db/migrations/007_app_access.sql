-- app: least-privilege access for the web API (role safescale_app) and its rate-limit table.
-- On Supabase an admin creates the role first (with a password; see SPEC-app.md). Locally it is
-- created here, without login, so tests can assume it exists.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'safescale_app') then
    create role safescale_app nologin;
  end if;
end
$$;

grant usage on schema public to safescale_app;

-- Read what analyze() and explain() need; nothing else (no ingest_runs, no schema_migrations).
grant select on recalls, recall_embeddings, recall_hazards, recall_standard_violations,
                hazard_categories, recall_term_df, recall_hazard_term_df to safescale_app;
grant execute on function search_recalls_vector(vector, int),
                          search_recalls_keyword(text, int),
                          search_recalls_hybrid(text, vector, int, int, int) to safescale_app;

-- The search functions run as the caller (security invoker), so RLS applies: allow reads for
-- safescale_app only. Supabase's anon / authenticated roles still have no policy and see nothing.
create policy app_read on recalls                    for select to safescale_app using (true);
create policy app_read on recall_embeddings          for select to safescale_app using (true);
create policy app_read on recall_hazards             for select to safescale_app using (true);
create policy app_read on recall_standard_violations for select to safescale_app using (true);
create policy app_read on hazard_categories          for select to safescale_app using (true);

-- Rate limiting: one row per (bucket, window). Buckets are salted hashes or 'global:*'; no IPs,
-- no product descriptions.
create table app_rate_limits (
  bucket       text        not null,
  window_start timestamptz not null,
  hits         int         not null check (hits > 0),
  primary key (bucket, window_start)
);

alter table app_rate_limits enable row level security;
grant select, insert, update, delete on app_rate_limits to safescale_app;
create policy app_limits on app_rate_limits for all to safescale_app using (true) with check (true);
