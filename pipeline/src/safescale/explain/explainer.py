"""The model behind explanations: a small provider interface and its OpenAI implementation."""

from dataclasses import dataclass
from typing import Protocol

from safescale.explain.schema import ExplanationDraft

DEFAULT_MODEL = "gpt-6-luna"

# USD per 1M tokens (input, output) from OpenAI's pricing page, checked 2026-10-19.
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
}


class ExplainerError(RuntimeError):
    """The model could not produce a draft (API error, refusal, unparseable output)."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0  # includes reasoning tokens
    reasoning_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.reasoning_tokens + other.reasoning_tokens,
            self.cost_usd + other.cost_usd,
        )


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class Explainer(Protocol):
    model: str

    def draft(
        self, packet: dict, feedback: list[str] | None = None
    ) -> tuple[ExplanationDraft, Usage]: ...
