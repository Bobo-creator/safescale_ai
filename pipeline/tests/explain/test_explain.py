import dataclasses
import json

from fake_explainer import ExplainerError, ScriptedExplainer, grounded_draft, ungrounded_draft

from safescale.analysis.report import DISCLAIMER
from safescale.explain.explain import CAVEAT, INSUFFICIENT_NOTICE, explain
from safescale.explain.packet import build_packet
from safescale.explain.schema import ExplanationDraft
from safescale.explain.validate import validate


def test_grounded_first_try(analyzed):
    conn, report = analyzed
    explainer = ScriptedExplainer(grounded_draft)
    result = explain(conn, report, explainer=explainer)
    assert explainer.calls == [None]  # one call, no retry
    assert result.generated and result.summary and result.hazards and result.match_reasons
    v = result.validation
    assert v.first_try_clean and v.retries == 0 and not v.fallback_used and v.dropped == []
    assert result.usage.input_tokens == 1000 and result.model == "scripted"
    assert result.caveat == CAVEAT and result.disclaimer == DISCLAIMER


def test_retry_gets_the_problems_as_feedback_then_succeeds(analyzed):
    conn, report = analyzed
    explainer = ScriptedExplainer(ungrounded_draft, grounded_draft)
    result = explain(conn, report, explainer=explainer)
    first, second = explainer.calls
    assert first is None and any("non-advisory wording 'safe'" in f for f in second)
    v = result.validation
    assert v.retries == 1 and not v.first_try_clean and not v.fallback_used
    assert len(v.dropped) == 3  # all from the first attempt
    assert result.usage.input_tokens == 2000


def test_fallback_summary_when_the_retry_also_fails(analyzed):
    conn, report = analyzed
    result = explain(conn, report, explainer=ScriptedExplainer(ungrounded_draft, ungrounded_draft))
    assert result.validation.fallback_used and result.summary
    assert not result.generated  # nothing the model wrote survived
    check = validate(
        ExplanationDraft(
            summary=result.summary, hazards=[], match_reasons=[], investigation_notes=[]
        ),
        build_packet(conn, report).grounding,
    )
    assert check.dropped == []  # the fallback is grounded by construction


def test_model_error_gives_a_deterministic_explanation(analyzed):
    conn, report = analyzed
    result = explain(conn, report, explainer=ScriptedExplainer(ExplainerError("rate limited")))
    assert result.summary and not result.generated
    assert result.validation.error == "rate limited" and result.validation.fallback_used


def test_insufficient_evidence_makes_no_model_call(analyzed):
    conn, report = analyzed
    report = dataclasses.replace(report, insufficient_evidence=True)
    explainer = ScriptedExplainer()
    result = explain(conn, report, explainer=explainer)
    assert explainer.calls == [] and result.notice == INSUFFICIENT_NOTICE
    assert not result.generated and result.summary == [] and result.model is None


def test_to_dict_is_json_ready(analyzed):
    conn, report = analyzed
    explainer = ScriptedExplainer(ungrounded_draft, grounded_draft)
    data = json.loads(json.dumps(explain(conn, report, explainer=explainer).to_dict()))
    assert data["summary"][0]["citations"] and data["validation"]["dropped"][0]["reason"]
    assert data["disclaimer"] == DISCLAIMER and data["prompt_version"] == 1
