"""Search recalls by product description: vector, keyword, or hybrid (RRF)."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from safescale.retrieval.embedder import Embedder

Method = Literal["vector", "keyword", "hybrid"]
METHODS: tuple[Method, ...] = ("vector", "keyword", "hybrid")

_SQL = {
    "vector": "search_recalls_vector(%(embedding)s, %(k)s)",
    "keyword": "search_recalls_keyword(%(query)s, %(k)s)",
    "hybrid": "search_recalls_hybrid(%(query)s, %(embedding)s, %(k)s)",
}


@dataclass(frozen=True)
class Hit:
    recall_id: int
    rank: int  # 1-based
    score: float  # only comparable within one method
    title: str
    url: str
    recall_date: date


def search(
    conn: psycopg.Connection,
    query: str,
    *,
    k: int = 25,
    method: Method = "vector",
    embedder: Embedder | None = None,
    query_embedding: list[float] | None = None,
) -> list[Hit]:
    """Top-k recalls for a description. Pass `query_embedding` (made by `embedder`) to reuse a
    vector the caller already has instead of embedding the query again."""
    query = " ".join(query.split())
    if not query:
        raise ValueError("query is empty")
    if k < 1:
        raise ValueError("k must be at least 1")
    if method not in _SQL:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")

    params: dict[str, object] = {"query": query, "k": k}
    if method != "keyword":
        if embedder is None:
            raise ValueError(f"method {method!r} needs an embedder")
        register_vector(conn)
        _check_model(conn, embedder.model)
        [vector] = [query_embedding] if query_embedding is not None else embedder.embed([query])
        params["embedding"] = Vector(vector)

    rows = conn.execute(
        f"select s.recall_id, s.rank, s.score, r.title, r.url, r.recall_date "
        f"from {_SQL[method]} s join recalls r using (recall_id) order by s.rank",
        params,
    ).fetchall()
    return [Hit(*row) for row in rows]


def _check_model(conn: psycopg.Connection, model: str) -> None:
    """Refuse to compare a query vector with document vectors from a different model."""
    row = conn.execute("select model from recall_embeddings limit 1").fetchone()
    if row is not None and row[0] != model:
        raise ValueError(f"recalls are embedded with {row[0]!r}, but the query uses {model!r}")
