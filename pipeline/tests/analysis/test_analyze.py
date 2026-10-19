import pytest
from fake_embedder import FakeEmbedder

from safescale.analysis.analyze import base_rates, build_matches
from safescale.retrieval.index import embed_recalls
from safescale.retrieval.search import METHODS, search
from safescale.taxonomy.store import classify_all

LITHIUM_QUERY = "lithium-ion battery pack overheating fire"
LITHIUM_RECALL_ID = 166
FAKE_FLOOR = 0.1  # the bag-of-words fake gives lower cosines than OpenAI embeddings


@pytest.fixture
def ready(fixture_recalls):
    """Fixture recalls, classified and embedded with the fake embedder."""
    classify_all(fixture_recalls)
    embed_recalls(fixture_recalls, FakeEmbedder())
    return fixture_recalls


def test_search_reuses_a_given_query_embedding(ready):
    class Counting(FakeEmbedder):
        calls = 0

        def embed(self, texts):
            Counting.calls += 1
            return super().embed(texts)

    embedder = Counting()
    vector = embedder.embed([LITHIUM_QUERY])[0]
    hits = search(ready, LITHIUM_QUERY, k=3, embedder=embedder, query_embedding=vector)
    assert Counting.calls == 1 and hits[0].recall_id == LITHIUM_RECALL_ID


@pytest.mark.parametrize("method", METHODS)
def test_matches_get_cosine_labels_for_any_method(ready, method):
    embedder = FakeEmbedder()
    vector = embedder.embed([LITHIUM_QUERY])[0]
    hits = search(ready, LITHIUM_QUERY, k=5, method=method, embedder=embedder)
    matches = build_matches(ready, hits, vector, relevance_floor=FAKE_FLOOR)
    assert [m.recall_id for m in matches] == [h.recall_id for h in hits]
    top = next(m for m in matches if m.recall_id == LITHIUM_RECALL_ID)
    assert 0 < top.cosine <= 1 and top.relevant
    assert [lbl.category for lbl in top.labels] == ["fire_overheating"]
    if method == "vector":
        assert all(m.cosine == pytest.approx(m.score) for m in matches)


def test_matches_without_embedding_are_weak(ready):
    ready.execute("delete from recall_embeddings where recall_id = %s", (LITHIUM_RECALL_ID,))
    hits = search(ready, LITHIUM_QUERY, k=3, method="keyword")
    vector = FakeEmbedder().embed([LITHIUM_QUERY])[0]
    matches = build_matches(ready, hits, vector, relevance_floor=FAKE_FLOOR)
    lithium = next(m for m in matches if m.recall_id == LITHIUM_RECALL_ID)
    assert lithium.cosine == 0 and not lithium.relevant and lithium.labels


def test_base_rates(ready):
    rates = base_rates(ready)
    assert set(rates) <= {
        "fire_overheating",
        "burn",
        "electrical_shock",
        "choking",
        "suffocation_strangulation",
        "laceration",
        "fall",
        "entrapment",
        "poisoning",
        "crash_loss_of_control",
        "drowning",
        "other",
    }
    assert all(0 < r <= 1 for r in rates.values())
    assert rates["fire_overheating"] == pytest.approx(
        ready.execute(
            "select count(*)::float / 18 from recall_hazards where category = 'fire_overheating'"
        ).fetchone()[0]
    )


# --- analyze() end to end -----------------------------------------------------------------------

import json  # noqa: E402

from safescale import cli  # noqa: E402
from safescale.analysis.analyze import analyze  # noqa: E402
from safescale.analysis.report import DISCLAIMER  # noqa: E402
from safescale.analysis.terms import refresh_term_stats  # noqa: E402
from safescale.analysis.text import format_report  # noqa: E402


@pytest.fixture
def analyzable(ready):
    refresh_term_stats(ready)
    return ready


def _report_ids(report):
    data = report.to_dict()
    ids = set()
    for section in ("profile", "shared_terms", "failure_terms", "investigation_areas", "standards"):
        for item in data[section]:
            ids |= set(item["recall_ids"])
    return ids


@pytest.mark.parametrize("method", METHODS)
def test_analyze_end_to_end(analyzable, method):
    report = analyze(
        analyzable,
        LITHIUM_QUERY,
        embedder=FakeEmbedder(),
        k=10,
        method=method,
        relevance_floor=FAKE_FLOOR,
    )
    # keyword only returns recalls that share a word with the query (7 of the 18 fixtures here)
    assert len(report.matches) == (7 if method == "keyword" else 10) and report.relevant >= 1
    assert report.profile and report.profile[0].count >= 1
    relevant_ids = {m.recall_id for m in report.matches if m.relevant}
    assert _report_ids(report) <= relevant_ids
    assert report.disclaimer == DISCLAIMER
    data = json.loads(json.dumps(report.to_dict()))
    assert data["query"] == LITHIUM_QUERY and data["matches"][0]["recall_date"]


def test_analyze_embeds_the_query_once(analyzable):
    class Counting(FakeEmbedder):
        calls = 0

        def embed(self, texts):
            Counting.calls += 1
            return super().embed(texts)

    analyze(analyzable, LITHIUM_QUERY, embedder=Counting(), k=5, method="hybrid")
    assert Counting.calls == 1


def test_no_relevant_matches_gives_insufficient_evidence(analyzable):
    report = analyze(analyzable, LITHIUM_QUERY, embedder=FakeEmbedder(), k=5, relevance_floor=0.99)
    assert report.relevant == 0 and report.insufficient_evidence
    assert report.overall_signal == "LOW" and not report.signal_drivers
    assert report.profile == [] and report.investigation_areas == [] and report.shared_terms == []
    assert "not enough historical evidence" in format_report(report)


def test_text_report_wording(analyzable):
    report = analyze(
        analyzable, LITHIUM_QUERY, embedder=FakeEmbedder(), k=10, relevance_floor=FAKE_FLOOR
    )
    text = format_report(report)
    assert text.startswith("Historical signal: ") and text.endswith(DISCLAIMER)
    body = text.removesuffix(DISCLAIMER).lower()
    for banned in (" safe ", "compliant", "certif", "probability"):
        assert banned not in body


def test_analyze_rejects_empty_query(analyzable):
    with pytest.raises(ValueError, match="empty"):
        analyze(analyzable, "   ", embedder=FakeEmbedder())


def test_cli_analyze_text_and_json(analyzable, monkeypatch, capsys):
    from tests_support import TEST_DATABASE_URL

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(cli, "make_embedder", FakeEmbedder)
    assert cli.main(["analyze", LITHIUM_QUERY, "--k", "5"]) == 0
    assert capsys.readouterr().out.startswith("Historical signal: ")
    assert cli.main(["analyze", LITHIUM_QUERY, "--k", "5", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["k"] == 5 and data["disclaimer"] == DISCLAIMER
