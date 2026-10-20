# SafeScale AI

**AI-powered product safety hazard intelligence.**

SafeScale AI compares a new consumer product concept against historical recalls and safety
incidents to surface evidence-backed hazard signals and the areas engineers should investigate
before manufacturing.

> **Core question:** *"What has gone wrong with products similar to mine, and what safety issues
> should I investigate before moving further toward manufacturing?"*

> **Disclaimer:** SafeScale AI does not certify that a product is safe or compliant. It identifies
> historically supported hazard signals and evidence that engineers should investigate further.

## How it works

1. **Describe** a product: function, components, materials, power/battery, intended users.
2. **Retrieve:** the description is embedded and matched against ~10,000 U.S. CPSC recall
   records using vector similarity (k-NN), with a BM25 keyword baseline for comparison.
3. **Analyze:** retrieved recalls are mapped to normalized hazard categories (fire/overheating,
   burn, shock, choking, laceration, fall, poisoning, entrapment) to build a hazard profile and a
   LOW / MODERATE / HIGH historical signal.
4. **Explain:** an LLM summarizes the evidence in plain language, citing only retrieved records.
5. **Recommend:** the dashboard lists investigation and test areas justified by the evidence.

The hazard profile describes *retrieved recalled products*. It is **not** the probability that
a new product will fail.

## Status

Early development: CS Seminar MVP (Layer 1: Product Hazard Intelligence).

| Module | Spec | Status |
|---|---|---|
| data-ingest | [SPEC-data-ingest.md](SPEC-data-ingest.md) | Done: 10,039 recalls in Supabase |
| hazard-taxonomy | [SPEC-hazard-taxonomy.md](SPEC-hazard-taxonomy.md) | Done: 12 hazard categories + standards flag; micro-F1 0.92 on a blind 50-recall gold set |
| retrieval | [SPEC-retrieval.md](SPEC-retrieval.md) | Done: 10,039 recalls embedded; vector / keyword / hybrid search |
| hazard-analysis | [SPEC-hazard-analysis.md](SPEC-hazard-analysis.md) | Done: hazard profile with lift, LOW / MODERATE / HIGH signal, shared and failure terms, investigation areas, cited standards |
| explain | [SPEC-explain.md](SPEC-explain.md) | Done: cited, validated explanations (gpt-6-luna, ~$0.001 each) |
| app | [SPEC-app.md](SPEC-app.md) | Live: **https://safescale-ai.vercel.app** (FastAPI + Next.js on Vercel) |
| evaluation | — | Not started |

See [CAPABILITY_MAP.md](CAPABILITY_MAP.md) for module boundaries, build order and key decisions.

## Tech stack

| Layer | Choice |
|---|---|
| Data pipeline | Python 3.12, `uv`, `httpx`, `pydantic`, `psycopg` |
| Database | PostgreSQL 17 + `pgvector` (Supabase in production, Homebrew locally) |
| Embeddings | OpenAI `text-embedding-3-small` (open-source model benchmarked in evaluation) |
| LLM explanation | OpenAI, grounded in retrieved records only |
| API | FastAPI |
| Frontend | Next.js / React |
| Hosting | Vercel + Supabase |
| Data source | [CPSC Recalls API](https://www.saferproducts.gov/RestWebServices/Recall) (U.S.) |

## Getting started (pipeline)

```bash
brew install uv postgresql@17 pgvector && brew services start postgresql@17
createdb safescale && createdb safescale_test
cp .env.example .env
cd pipeline && uv sync
uv run safescale migrate      # create tables
uv run safescale ingest       # download all CPSC recalls (~10k) and load them
uv run safescale classify     # label every recall with hazard categories (~5 s)
uv run safescale embed        # embed new/changed recalls with OpenAI (needs OPENAI_API_KEY)
uv run safescale hazards 166  # a recall's hazard labels and the phrases behind them
uv run safescale analyze "rechargeable night light, lithium-ion battery, USB-C"   # hazard report
uv run safescale analyze "..." --k 50 --method hybrid --json                      # as JSON
uv run safescale explain "rechargeable night light, lithium-ion battery, USB-C"   # + explanation
uv run safescale search "rechargeable night light, lithium-ion battery" --method hybrid
uv run safescale label        # local page for labeling the gold sample
uv run safescale score-hazards  # classifier vs your gold labels: P / R / F1
uv run pytest                 # offline tests (use the safescale_test database)
uv run pytest -m live         # optional: one real OpenAI call
```

### Supabase

Production data lives in the Supabase project `safescale-ai` (`us-east-1`, Postgres 17). The
pipeline connects through the **session pooler** as a dedicated `safescale_pipeline` role, which
can create and write its own tables in `public` but is not a superuser:

```sql
create role safescale_pipeline login password '<secret>';
grant usage, create on schema public to safescale_pipeline;
```

Its connection string lives only in `.env` (git-ignored). To run the pipeline against your
local database instead, override it: `DATABASE_URL=postgresql://localhost/safescale uv run safescale ingest`.
All tables have RLS enabled with no policies, so the public Data API cannot read them until the
`app` module defines access.

## Repository layout (planned)

```
pipeline/        Python: ingestion, hazard labeling, embeddings, evaluation
db/migrations/   SQL migrations (applied to local Postgres and Supabase)
api/             FastAPI service
web/             Next.js dashboard
data/            Local raw snapshots (git-ignored)
```

## Roadmap

- **Layer 1, Product Hazard Intelligence (now):** public recall data → similar failures and hazard signals.
- **Layer 2, BOM & Compliance Intelligence (next):** BOMs, SDS, supplier documents, regulatory rules.
- **Layer 3, Manufacturing Scale-Up Prediction (long-term):** proprietary production data →
  failure prediction during scale-up.

## Research question

*Can semantic retrieval of historical product-safety records identify relevant hazard patterns
for previously unseen product descriptions?* We evaluate vector vs BM25 vs hybrid retrieval with
Precision@K, Recall@K and NDCG@K on a hand-labeled query set, plus precision/recall/F1 for hazard
classification.
