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
