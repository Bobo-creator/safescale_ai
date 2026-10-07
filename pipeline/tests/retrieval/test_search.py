import pytest
from fake_embedder import FakeEmbedder

from safescale.retrieval.index import embed_recalls
from safescale.retrieval.search import METHODS, search

LITHIUM_QUERY = "lithium-ion battery pack overheating fire"


@pytest.fixture
def indexed(fixture_recalls):
    embed_recalls(fixture_recalls, FakeEmbedder())
    return fixture_recalls


LITHIUM_RECALL_ID = 166  # fixture chosen for its lithium-ion fire hazard (fixtures/README.md)


@pytest.mark.parametrize("method", METHODS)
def test_lithium_query_ranks_lithium_recall_first(indexed, method):
    hits = search(indexed, LITHIUM_QUERY, k=5, method=method, embedder=FakeEmbedder())
    assert hits[0].recall_id == LITHIUM_RECALL_ID


@pytest.mark.parametrize("method", METHODS)
def test_returns_k_ranked_hits_with_metadata(indexed, method):
    # Common recall words, so every method has more than k candidates.
    query = "consumers should stop using the recalled products"
    hits = search(indexed, query, k=4, method=method, embedder=FakeEmbedder())
    assert [h.rank for h in hits] == [1, 2, 3, 4]
    assert all(h.title and h.url.startswith("https://") for h in hits)


def test_long_natural_language_query_gets_keyword_hits(indexed):
    query = (
        "Rechargeable children's night light using a 2000 mAh lithium-ion battery, USB-C "
        "charging, ABS plastic housing, and LED lighting for the bedroom"
    )
    assert len(search(indexed, query, k=5, method="keyword")) == 5


def test_stopword_only_keyword_query_returns_nothing(indexed):
    assert search(indexed, "the and of", k=5, method="keyword") == []


def test_keyword_needs_no_embedder(indexed):
    search(indexed, LITHIUM_QUERY, method="keyword")


def test_vector_without_embedder_is_an_error(indexed):
    with pytest.raises(ValueError, match="needs an embedder"):
        search(indexed, LITHIUM_QUERY, method="vector")


def test_mismatched_model_is_refused(indexed):
    other = FakeEmbedder()
    other.model = "something-else"
    with pytest.raises(ValueError, match="embedded with"):
        search(indexed, LITHIUM_QUERY, method="vector", embedder=other)


@pytest.mark.parametrize(("query", "k"), [("   ", 5), ("ok", 0)])
def test_bad_input(indexed, query, k):
    with pytest.raises(ValueError):
        search(indexed, query, k=k, method="keyword")
