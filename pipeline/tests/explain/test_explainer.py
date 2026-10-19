from types import SimpleNamespace

import openai
import pytest

from safescale.explain.explainer import ExplainerError, OpenAIExplainer, Usage, cost
from safescale.explain.prompt import INSTRUCTIONS
from safescale.explain.schema import ExplanationDraft, Sentence

DRAFT = ExplanationDraft(
    summary=[Sentence(text="Fire recurs.", citations=[1])],
    hazards=[],
    match_reasons=[],
    investigation_notes=[],
)


class FakeResponses:
    def __init__(self, parsed=DRAFT, error=None):
        self.parsed, self.error, self.kwargs = parsed, error, None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        usage = SimpleNamespace(
            input_tokens=6000,
            output_tokens=1500,
            output_tokens_details=SimpleNamespace(reasoning_tokens=700),
        )
        return SimpleNamespace(output_parsed=self.parsed, usage=usage)


def client(**kw):
    return SimpleNamespace(responses=FakeResponses(**kw))


def test_request_shape_and_usage(monkeypatch):
    monkeypatch.delenv("EXPLAIN_MODEL", raising=False)
    c = client()
    draft, usage = OpenAIExplainer(client=c).draft({"recalls": []}, feedback=["summary[0]: bad"])
    kw = c.responses.kwargs
    assert kw["model"] == "gpt-6-luna" and kw["text_format"] is ExplanationDraft
    assert kw["instructions"] == INSTRUCTIONS and kw["reasoning"] == {"effort": "low"}
    assert '"recalls": []' in kw["input"] and "summary[0]: bad" in kw["input"]
    assert draft == DRAFT
    assert usage == Usage(6000, 1500, 700, cost("gpt-6-luna", 6000, 1500))
    assert usage.cost_usd == pytest.approx(0.00135)


def test_model_from_environment(monkeypatch):
    monkeypatch.setenv("EXPLAIN_MODEL", "gpt-6.1-sol")
    assert OpenAIExplainer(client=client()).model == "gpt-6.1-sol"


def test_refusal_and_api_errors_become_explainer_errors():
    with pytest.raises(ExplainerError, match="no parsable answer"):
        OpenAIExplainer(client=client(parsed=None)).draft({})
    error = openai.APIConnectionError(request=None)
    with pytest.raises(ExplainerError, match="APIConnectionError"):
        OpenAIExplainer(client=client(error=error)).draft({})


def test_unknown_model_costs_zero_rather_than_guessing():
    assert cost("some-future-model", 1000, 1000) == 0.0
