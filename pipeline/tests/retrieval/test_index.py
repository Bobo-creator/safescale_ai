from fake_embedder import FakeEmbedder

from safescale.retrieval.index import embed_recalls


def count(conn, sql="select count(*) from recall_embeddings"):
    return conn.execute(sql).fetchone()[0]


def test_embeds_everything_then_nothing(fixture_recalls):
    embedder = FakeEmbedder()
    assert embed_recalls(fixture_recalls, embedder).embedded == 18
    assert count(fixture_recalls) == 18
    assert embed_recalls(fixture_recalls, embedder).embedded == 0
    assert embedder.calls[-1:] != [[]]  # no empty request was sent


def test_limit(fixture_recalls):
    assert embed_recalls(fixture_recalls, FakeEmbedder(), limit=5).embedded == 5
    assert embed_recalls(fixture_recalls, FakeEmbedder()).embedded == 13


def test_changed_document_is_re_embedded_alone(fixture_recalls):
    embedder = FakeEmbedder()
    embed_recalls(fixture_recalls, embedder)
    fixture_recalls.execute(
        "update recalls set document = document || ' (revised)', content_hash = 'changed' "
        "where recall_id = 166"
    )
    embedder.calls.clear()
    assert embed_recalls(fixture_recalls, embedder).embedded == 1
    assert len(embedder.calls) == 1 and embedder.calls[0][0].endswith("(revised)")


def test_model_change_re_embeds_everything(fixture_recalls):
    embed_recalls(fixture_recalls, FakeEmbedder())
    other = FakeEmbedder()
    other.model = "fake-bow-v2"
    assert embed_recalls(fixture_recalls, other).embedded == 18
    models = fixture_recalls.execute("select distinct model from recall_embeddings").fetchall()
    assert models == [("fake-bow-v2",)]
