"""The model behind explanations: a small provider interface and its OpenAI implementation."""

import os
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from safescale.explain.prompt import INSTRUCTIONS, build_input
from safescale.explain.schema import ExplanationDraft

DEFAULT_MODEL = "gpt-6-luna"
# Benchmarked 2026-10-19 on 10 queries: "none" was as clean as "low" (10/10 vs 9/10 first try),
# faster (median 8.3 s vs 9.7 s) and cheaper. Values differ per model ("minimal" is not luna's).
DEFAULT_EFFORT = "none"

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


class OpenAIExplainer:
    """Structured output from the OpenAI Responses API, parsed into ExplanationDraft."""

    def __init__(self, client=None, model: str | None = None, effort: str | None = None):
        import openai

        self._openai = openai
        self.client = client or openai.OpenAI()
        self.model = model or os.environ.get("EXPLAIN_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("EXPLAIN_REASONING_EFFORT", DEFAULT_EFFORT)

    def draft(
        self, packet: dict, feedback: list[str] | None = None
    ) -> tuple[ExplanationDraft, Usage]:
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=INSTRUCTIONS,
                input=build_input(packet, feedback),
                text_format=ExplanationDraft,
                reasoning={"effort": self.effort},
            )
        except (self._openai.OpenAIError, ValidationError) as exc:
            raise ExplainerError(f"{type(exc).__name__}: {exc}") from exc
        parsed = response.output_parsed
        if parsed is None:
            raise ExplainerError("the model returned no parsable answer (refusal or empty)")
        u = response.usage
        details = getattr(u, "output_tokens_details", None)
        usage = Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            reasoning_tokens=getattr(details, "reasoning_tokens", 0) or 0,
            cost_usd=cost(self.model, u.input_tokens, u.output_tokens),
        )
        return parsed, usage
