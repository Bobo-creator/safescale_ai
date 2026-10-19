"""One real explanation (opt-in: uv run pytest -m live). Costs well under a cent."""

import pytest

from safescale.explain.explain import explain
from safescale.explain.explainer import OpenAIExplainer


@pytest.mark.live
def test_real_explanation_passes_validation(analyzed):
    conn, report = analyzed
    result = explain(conn, report, explainer=OpenAIExplainer())
    assert result.generated and result.summary
    assert not result.validation.fallback_used
    assert all(s.citations for s in result.summary)
    assert result.usage.input_tokens > 0 and result.usage.cost_usd < 0.01
