"""Text embedders. Production uses OpenAI; tests use a deterministic fake (see tests/)."""

import logging
import os
from collections.abc import Iterator
from typing import Protocol

from openai import OpenAI

log = logging.getLogger(__name__)

DEFAULT_MODEL = "text-embedding-3-small"
DIMENSIONS = 1536  # must match vector(1536) in db/migrations/002_retrieval.sql

# OpenAI limits per request: 2,048 inputs and 300,000 tokens. Stay well under both; tokens are
# estimated as chars/3, which over-counts for English (~4 chars per token).
MAX_BATCH_ITEMS = 256
MAX_BATCH_TOKENS = 250_000


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def estimate_tokens(text: str) -> int:
    return len(text) // 3 + 1


def batches(
    texts: list[str], max_items: int = MAX_BATCH_ITEMS, max_tokens: int = MAX_BATCH_TOKENS
) -> Iterator[list[str]]:
    """Split texts into consecutive batches that respect both request limits."""
    batch: list[str] = []
    tokens = 0
    for text in texts:
        cost = estimate_tokens(text)
        if batch and (len(batch) == max_items or tokens + cost > max_tokens):
            yield batch
            batch, tokens = [], 0
        batch.append(text)
        tokens += cost
    if batch:
        yield batch


class OpenAIEmbedder:
    """Embeds texts with the OpenAI API, batching requests and tracking token usage."""

    def __init__(self, client: OpenAI | None = None, model: str | None = None) -> None:
        self.client = client or OpenAI()  # reads OPENAI_API_KEY; SDK retries rate limits
        self.model = model or os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
        self.total_tokens = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch in batches(texts):
            response = self.client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            if len(ordered) != len(batch):
                raise RuntimeError(f"asked for {len(batch)} embeddings, got {len(ordered)}")
            for item in ordered:
                if len(item.embedding) != DIMENSIONS:
                    raise RuntimeError(
                        f"{self.model} returned {len(item.embedding)} dimensions, "
                        f"expected {DIMENSIONS}"
                    )
                vectors.append(item.embedding)
            self.total_tokens += response.usage.total_tokens
            log.debug("embedded batch of %d (%d tokens)", len(batch), response.usage.total_tokens)
        return vectors
