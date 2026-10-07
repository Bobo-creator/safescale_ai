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
| data-ingest | [SPEC-data-ingest.md](SPEC-data-ingest.md) | Spec drafted |
| hazard-taxonomy | — | Not started |
| retrieval | — | Not started |
| hazard-analysis | — | Not started |
| explain | — | Not started |
| app | — | Not started |
| evaluation | — | Not started |

See [CAPABILITY_MAP.md](CAPABILITY_MAP.md) for module boundaries, build order and key decisions.

## Tech stack

| Layer | Choice |
|---|---|
| Data pipeline | Python 3.12, `uv`, `httpx`, `pydantic`, `psycopg` |
| Database | PostgreSQL + `pgvector` (Supabase in production, Docker locally) |
| Embeddings | OpenAI `text-embedding-3-small` (open-source model benchmarked in evaluation) |
| LLM explanation | OpenAI, grounded in retrieved records only |
| API | FastAPI |
| Frontend | Next.js / React |
| Hosting | Vercel + Supabase |
| Data source | [CPSC Recalls API](https://www.saferproducts.gov/RestWebServices/Recall) (U.S.) |

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
