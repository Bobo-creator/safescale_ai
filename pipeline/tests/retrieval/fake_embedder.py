"""Deterministic offline embedder: hashed bag of words, L2-normalized.

Texts sharing words get high cosine similarity, which is enough to test ranking logic without
calling OpenAI.
"""

import hashlib
import math
import re

from safescale.retrieval.embedder import DIMENSIONS

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on", "is", "are"}


class FakeEmbedder:
    model = "fake-bow"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in _WORD.findall(text.lower()):
            if word not in _STOPWORDS:
                bucket = int.from_bytes(hashlib.md5(word.encode()).digest()[:4], "big")
                vector[bucket % DIMENSIONS] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
