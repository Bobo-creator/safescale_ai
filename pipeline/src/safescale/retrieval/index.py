"""`safescale embed`: embed recalls that are new or whose document/model changed."""

import logging
from dataclasses import dataclass

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from safescale.retrieval.embedder import MAX_BATCH_ITEMS, Embedder

log = logging.getLogger(__name__)

_STALE = """
select r.recall_id, r.document, r.content_hash
from recalls r
left join recall_embeddings e using (recall_id)
where e.recall_id is null or e.content_hash <> r.content_hash or e.model <> %(model)s
order by r.recall_id
limit %(limit)s
"""

_UPSERT = """
insert into recall_embeddings (recall_id, model, content_hash, embedding)
values (%s, %s, %s, %s)
on conflict (recall_id) do update
set model = excluded.model, content_hash = excluded.content_hash,
    embedding = excluded.embedding, embedded_at = now()
"""


@dataclass(frozen=True)
class EmbedResult:
    embedded: int
    tokens: int  # as reported by the API (0 for embedders that don't track usage)


def embed_recalls(
    conn: psycopg.Connection, embedder: Embedder, *, limit: int | None = None
) -> EmbedResult:
    """Embed stale recalls in chunks; each chunk commits, so an interrupted run can resume."""
    register_vector(conn)
    stale = conn.execute(_STALE, {"model": embedder.model, "limit": limit}).fetchall()
    log.info("%d recalls need embedding with %s", len(stale), embedder.model)

    tokens_before = getattr(embedder, "total_tokens", 0)
    for start in range(0, len(stale), MAX_BATCH_ITEMS):
        chunk = stale[start : start + MAX_BATCH_ITEMS]
        vectors = embedder.embed([document for _, document, _ in chunk])
        with conn.transaction(), conn.cursor() as cur:
            cur.executemany(
                _UPSERT,
                [
                    (recall_id, embedder.model, content_hash, Vector(vector))
                    for (recall_id, _, content_hash), vector in zip(chunk, vectors, strict=True)
                ],
            )
        log.info("embedded %d/%d", start + len(chunk), len(stale))

    tokens = getattr(embedder, "total_tokens", 0) - tokens_before
    return EmbedResult(embedded=len(stale), tokens=tokens)
