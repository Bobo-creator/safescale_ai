import pytest
from fake_embedder import FakeEmbedder

from safescale.analysis.analyze import analyze
from safescale.analysis.terms import refresh_term_stats
from safescale.retrieval.index import embed_recalls
from safescale.taxonomy.store import classify_all

LITHIUM_QUERY = "lithium-ion battery pack overheating fire"
FAKE_FLOOR = 0.0  # explain tests are about the flow, not relevance: count every fixture recall


@pytest.fixture
def analyzed(fixture_recalls):
    """(conn, report) for the lithium query over the classified, embedded fixture recalls."""
    classify_all(fixture_recalls)
    refresh_term_stats(fixture_recalls)
    embed_recalls(fixture_recalls, FakeEmbedder())
    report = analyze(
        fixture_recalls, LITHIUM_QUERY, embedder=FakeEmbedder(), k=18, relevance_floor=FAKE_FLOOR
    )
    return fixture_recalls, report
