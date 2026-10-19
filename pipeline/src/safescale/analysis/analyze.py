"""analyze(): retrieval + stored hazard labels + term statistics -> HazardReport."""

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from safescale.analysis.report import RELEVANCE_FLOOR, Match
from safescale.retrieval.search import Hit
from safescale.taxonomy.store import labels_for

_COSINES = """
select r.recall_id, 1 - (e.embedding <=> %s), r.hazard_text
from recalls r left join recall_embeddings e using (recall_id)
where r.recall_id = any(%s)
"""


def build_matches(
    conn: psycopg.Connection,
    hits: list[Hit],
    query_embedding: list[float],
    *,
    relevance_floor: float = RELEVANCE_FLOOR,
) -> list[Match]:
    """Attach cosine similarity (for any retrieval method), hazard labels and violations.

    A hit without a stored embedding gets cosine 0, so it is listed but never counted.
    """
    ids = [hit.recall_id for hit in hits]
    register_vector(conn)
    rows = conn.execute(_COSINES, (Vector(query_embedding), ids)).fetchall()
    cosines = {rid: cos for rid, cos, _ in rows if cos is not None}
    hazard_texts = {rid: text for rid, _, text in rows}
    labels = labels_for(conn, ids)
    matches = []
    for hit in hits:
        classification = labels.get(hit.recall_id)
        cosine = float(cosines.get(hit.recall_id, 0.0))
        matches.append(
            Match(
                recall_id=hit.recall_id,
                rank=hit.rank,
                score=hit.score,
                cosine=cosine,
                title=hit.title,
                url=hit.url,
                recall_date=hit.recall_date,
                labels=classification.labels if classification else [],
                violations=classification.violations if classification else [],
                relevant=cosine >= relevance_floor,
                hazard_text=hazard_texts.get(hit.recall_id),
            )
        )
    return matches


def base_rates(conn: psycopg.Connection) -> dict[str, float]:
    """Share of all recalls carrying each hazard category."""
    rows = conn.execute(
        "select category, count(*)::float / greatest((select count(*) from recalls), 1) "
        "from recall_hazards group by category"
    ).fetchall()
    return dict(rows)
