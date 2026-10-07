# Capability Map: SafeScale AI — Layer 1 (Product Hazard Intelligence)

Source brief: `SafeScale_AI_Project_Brief.pdf` (CS Seminar MVP). This map is the index of
module specs; each module gets its own `SPEC-<module-id>.md`, written in build order.

| Module id | Responsibility | Depends on |
|---|---|---|
| data-ingest | Fetch CPSC recall records, clean text, store normalized records + original metadata/links | — |
| hazard-taxonomy | Map each record to normalized hazard categories (fire/overheating, burn, shock, choking, laceration, fall, poisoning, entrapment, other; multi-label) | data-ingest |
| retrieval | Embed records and queries, pgvector k-NN (cosine), BM25 baseline (Postgres full-text), hybrid mode | data-ingest |
| hazard-analysis | Hazard distribution over top-k, LOW/MODERATE/HIGH historical signal, shared components/phrases | retrieval, hazard-taxonomy |
| explain | LLM explanation grounded only in retrieved records; every claim cites a record id; fixed disclaimer | retrieval, hazard-analysis |
| app | FastAPI service + Next.js dashboard (query form, evidence cards, hazard profile, explanation, investigation areas) | hazard-analysis, explain |
| evaluation | Labeled query set; P@K / R@K / NDCG@K for vector vs BM25 vs hybrid across k; latency; hazard-label P/R/F1 | retrieval, hazard-taxonomy |

Build order: data-ingest → hazard-taxonomy, retrieval → hazard-analysis → explain → app.
evaluation starts once retrieval exists and runs alongside the rest.
Approach: a thin end-to-end slice first (small record subset, plain k-NN, minimal form), then deepen each module.

## Decisions

| Decision | Choice | Notes |
|---|---|---|
| LLM provider (explain) | OpenAI | Behind a small provider interface so it can be swapped |
| Embeddings (production) | OpenAI `text-embedding-3-small` | Same vendor/key as the LLM; no model to host |
| Embeddings (evaluation) | Also benchmark one open-source sentence-transformers model offline | Research comparison only; never deployed |
| Database | Supabase (managed Postgres + pgvector) | Vectors, metadata and full-text search in one place |
| Hosting | Vercel (Next.js + API) + Supabase | Add a separate Python host (Railway/Render) only if the API outgrows Vercel |
| Ingestion runtime | Run locally / scheduled job, writes to Supabase | Not part of the request path |
| Labeled test set | Claude drafts candidates; project owner reviews and labels | |
| Team / timeline | Solo builder, no fixed deadline | |
| Vector store | pgvector in Supabase (not Pinecone) | ~10k records; one DB for vectors, metadata and BM25 |

Data finding (2026-10-06): CPSC `HazardType` is empty on every record, so hazard-taxonomy must
classify from free text.

Out of scope for v1 (brief's nice-to-haves): auth, saved projects, BOM upload, HDBSCAN clustering, second jurisdiction.
