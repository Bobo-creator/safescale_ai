import json

from fake_embedder import FakeEmbedder
from fake_explainer import ScriptedExplainer, grounded_draft, ungrounded_draft
from tests_support import TEST_DATABASE_URL

from safescale import cli
from safescale.analysis.report import DISCLAIMER
from safescale.explain.explain import explain
from safescale.explain.text import format_explanation


def test_text_has_citations_references_caveat_and_disclaimer(analyzed):
    conn, report = analyzed
    exp = explain(conn, report, explainer=ScriptedExplainer(ungrounded_draft, grounded_draft))
    text = format_explanation(report, exp)
    assert text.startswith("Historical signal: ")
    first_cited = exp.summary[0].citations[0]
    assert f"[#{first_cited}]" in text
    references = text.split("References\n", 1)[1]
    assert f"[#{first_cited}]" in references and "https://www.cpsc.gov/" in references
    assert exp.caveat in text and DISCLAIMER in text
    assert "3 unsupported item(s) removed; retried once" in text


def test_cli_explain_json(analyzed, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(cli, "make_embedder", FakeEmbedder)
    monkeypatch.setattr(cli, "make_explainer", lambda model=None: ScriptedExplainer(grounded_draft))
    # With the real 0.30 floor the fake embedder finds no relevant recalls: insufficient evidence.
    assert cli.main(["explain", "lithium-ion battery pack overheating fire", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"report", "explanation"}
    assert data["explanation"]["notice"] and not data["explanation"]["generated"]
    assert cli.main(["explain", "lithium-ion battery pack overheating fire"]) == 0
    assert "not enough historical evidence" in capsys.readouterr().out
