-- data-ingest: normalized CPSC recall records and an audit log of ingest runs.
-- Vector / full-text columns are added later by the retrieval module.

create table recalls (
  recall_id              bigint primary key,          -- CPSC RecallID (natural key)
  recall_number          text,
  recall_date            date not null,
  last_publish_date      date,
  title                  text not null,
  description            text,
  url                    text not null,
  product_names          text[] not null default '{}',
  product_types          text[] not null default '{}',
  hazard_text            text,                        -- joined Hazards[].Name
  injuries_text          text,
  remedy_text            text,
  units_text             text,                        -- e.g. "About 165"
  manufacturer_countries text[] not null default '{}',
  document               text not null check (document <> ''),  -- canonical retrieval text
  content_hash           text not null,               -- sha256(document)
  raw                    jsonb not null,              -- original record, unmodified
  ingested_at            timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

create table ingest_runs (
  run_id          bigint generated always as identity primary key,
  started_at      timestamptz not null,
  finished_at     timestamptz,
  source          text not null check (source in ('api', 'snapshot')),
  snapshot_sha256 text not null,
  fetched         integer not null,
  inserted        integer not null,
  updated         integer not null,
  unchanged       integer not null,
  rejected        integer not null
);

-- Supabase exposes the public schema through its Data API. With RLS on and no policies,
-- only the pipeline's direct Postgres connection can read or write these tables until the
-- app module defines read access.
alter table recalls enable row level security;
alter table ingest_runs enable row level security;
