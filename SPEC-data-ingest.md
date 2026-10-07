# Spec: data-ingest

Module id: `data-ingest` (see [CAPABILITY_MAP.md](CAPABILITY_MAP.md)). Depends on: nothing.
Consumed by: `hazard-taxonomy`, `retrieval`, `evaluation`.

## Objective

Build a reproducible pipeline that downloads every U.S. CPSC recall record, cleans it, and stores
it in Postgres with its original metadata, so the downstream modules work from one trustworthy,
re-buildable table.

**User of this module:** the downstream modules (and the developer running the pipeline), not end users.

**Done looks like:** one command takes an empty database to a fully populated `recalls` table,
and re-running it changes nothing unless CPSC published changes.

## Source data (verified 2026-10-06)

- Endpoint: `GET https://www.saferproducts.gov/RestWebServices/Recall?format=json`
  - Optional filters: `RecallDateStart`, `RecallDateEnd` (`YYYY-MM-DD`).
- No API key. The full dataset is **10,039 records, 1973–2026, ~28 MB**, returned in a single
  request in ~1–2 s.
- Each record has: `RecallID` (unique), `RecallNumber`, `RecallDate`, `LastPublishDate`, `Title`,
  `Description`, `URL`, and lists `Products[]` (Name, Type, Model, NumberOfUnits…), `Hazards[]`
  (Name, HazardType), `Injuries[]`, `Remedies[]`, `ManufacturerCountries[]`, `Manufacturers[]`,
  `Retailers[]`, `Importers[]`, `Distributors[]`, `Images[]`, `ProductUPCs[]`.
- **Data-quality findings that matter downstream:**
  - `Hazards[].HazardType` is **empty on every sampled record**. Hazard categories must be
    derived from free text (`Hazards[].Name`, `Title`, `Description`), which is the job of `hazard-taxonomy`.
  - `Products[].Type` is filled for older recalls but empty for recent ones (e.g. all of 2023).
  - 169 records have no `Hazards` entries; 2 have no `Description`. Description length: median
    ~500 chars, p95 ~2,400 chars.

## Behavior

1. **Fetch:** download the full dataset in one request (paging by year is the fallback if the
   single request fails). Save the raw response to `data/raw/recalls_<UTC timestamp>.json` and
   record its SHA-256. `--snapshot PATH` skips the network and loads a saved file, which is how
   runs are reproduced.
2. **Parse:** validate each record with a Pydantic model. Records that fail validation are logged
   and counted, never silently dropped.
3. **Clean:** unescape HTML entities, strip HTML tags, collapse whitespace, turn `""` and
   placeholders such as `"None"` into `NULL`, dedupe and trim list values, and parse dates to `DATE`.
4. **Build `document`:** a canonical text field that `retrieval` (embeddings + BM25) uses:
   ```
   Title: <title>
   Products: <product names; types>
   Hazard: <hazard names>
   Description: <description>
   Injuries: <injury text>
   ```
   `content_hash = sha256(document)`, so downstream modules re-embed only rows that changed.
5. **Load:** upsert into `recalls` keyed on `recall_id`, in one transaction. Insert a row into
   `ingest_runs` recording counts and the snapshot hash.

## Data model (migration `db/migrations/001_recalls.sql`)

```sql
CREATE TABLE recalls (
  recall_id              INTEGER PRIMARY KEY,         -- CPSC RecallID
  recall_number          TEXT,
  recall_date            DATE NOT NULL,
  last_publish_date      DATE,
  title                  TEXT NOT NULL,
  description            TEXT,
  url                    TEXT NOT NULL,
  product_names          TEXT[] NOT NULL DEFAULT '{}',
  product_types          TEXT[] NOT NULL DEFAULT '{}',
  hazard_text            TEXT,                        -- joined Hazards[].Name
  injuries_text          TEXT,
  remedy_text            TEXT,
  units_text             TEXT,                        -- e.g. "About 165"
  manufacturer_countries TEXT[] NOT NULL DEFAULT '{}',
  document               TEXT NOT NULL,               -- canonical text for retrieval
  content_hash           TEXT NOT NULL,
  raw                    JSONB NOT NULL,              -- original record, unmodified
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ingest_runs (
  run_id           BIGSERIAL PRIMARY KEY,
  started_at       TIMESTAMPTZ NOT NULL,
  finished_at      TIMESTAMPTZ,
  source           TEXT NOT NULL,          -- 'api' | 'snapshot'
  snapshot_sha256  TEXT NOT NULL,
  fetched          INTEGER NOT NULL,
  inserted         INTEGER NOT NULL,
  updated          INTEGER NOT NULL,
  unchanged        INTEGER NOT NULL,
  rejected         INTEGER NOT NULL
);
```

Vector and full-text columns are **not** added here; `retrieval` adds them in its own migration.

## Tech stack

Python 3.12 managed with `uv`; `httpx` (fetch), `pydantic` v2 (validation), `psycopg` 3 (Postgres),
`pytest`, `ruff`. Local Postgres uses the `pgvector/pgvector:pg16` Docker image so it matches
Supabase. Migrations are plain SQL files applied in order by a small runner.

## Commands

```bash
docker compose up -d db                                     # local Postgres + pgvector
cd pipeline && uv sync                                      # install deps
uv run safescale migrate                                    # apply db/migrations/*.sql
uv run safescale ingest                                     # fetch from API → load
uv run safescale ingest --snapshot ../data/raw/<file>.json  # reproducible load from snapshot
uv run safescale ingest --limit 500                         # thin slice for early end-to-end work
uv run pytest                                               # tests
uv run ruff check . && uv run ruff format --check .         # lint
```

`DATABASE_URL` selects the target (local Docker by default, Supabase via `.env`).

## Project structure

```
docker-compose.yml
db/migrations/001_recalls.sql
data/raw/                          # snapshots (git-ignored)
pipeline/
  pyproject.toml
  src/safescale/
    cli.py                         # `safescale` entry point (migrate, ingest)
    db.py                          # connection + migration runner
    ingest/
      fetch.py                     # HTTP download + snapshot writing
      models.py                    # Pydantic models for raw CPSC records
      clean.py                     # pure text/field cleaning functions
      document.py                  # canonical `document` builder
      load.py                      # upsert + ingest_runs
  tests/
    fixtures/recalls_sample.json   # ~20 real records incl. edge cases
    ingest/test_clean.py
    ingest/test_document.py
    ingest/test_load.py            # against local Postgres
```

## Code style

Pure functions for transformation, side effects only at the edges (fetch, load). Type hints
everywhere; `ruff` defaults with line length 100.

```python
def clean_text(value: str | None) -> str | None:
    """Unescape HTML, strip tags, collapse whitespace; empty or placeholder -> None."""
    if value is None:
        return None
    text = _WHITESPACE.sub(" ", _TAGS.sub(" ", html.unescape(value))).strip()
    return None if text.lower() in _PLACEHOLDERS else text
```

## Testing strategy

- **Unit (pytest):** cleaning, parsing and document building against `fixtures/recalls_sample.json`,
  which holds real records chosen for edge cases (no hazards, no description, HTML entities,
  multiple products, 1970s record).
- **Integration:** loading into local Docker Postgres, covering a fresh insert, an idempotent
  re-run (0 inserted / 0 updated), and a changed record (exactly 1 updated).
- **No live API calls in tests.** The network is touched only by `safescale ingest` itself.

## Boundaries

- **Always:** keep the unmodified `raw` record; save a snapshot for every API fetch; make loads
  idempotent; log and count rejected records.
- **Ask first:** changing the `recalls` schema after downstream modules depend on it; adding a
  second data source; adding dependencies beyond the stack above.
- **Never:** commit snapshots or `.env` / credentials; drop records silently; call the live API from tests.

## Success criteria

1. `safescale ingest` against an empty database loads all CPSC recalls (≥ 10,000 rows) in under 2 minutes.
2. An immediate re-run reports `inserted=0, updated=0` and leaves `content_hash` values unchanged.
3. Every row has non-null `recall_id`, `recall_date`, `title`, `url` and a non-empty `document`.
4. `--snapshot` on the same file produces identical `content_hash` values (reproducible).
5. `rejected` is 0, or every rejected record is logged with its `RecallID` and reason.
6. Every run writes one `ingest_runs` row with the snapshot SHA-256.
7. Tests and lint pass.

## Open questions

1. **Incremental updates:** the API may support filtering on `LastPublishDate`. A full refresh
   takes ~1 s, so v1 always does a full refresh; incremental loading is deferred.
2. **Very old records (1970s–80s):** short descriptions, no injury data. Keep all of them for now;
   `evaluation` can test whether filtering by date helps retrieval.
3. **SaferProducts.gov incident reports** (consumer-submitted) would be a second source, out of
   scope until the recalls pipeline is stable.
4. **Supabase free tier** pauses inactive projects; acceptable for a demo, revisit before
   presenting it live.
