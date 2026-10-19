import http.client
import json
import threading

import pytest

from safescale.taxonomy.categories import CATEGORY_CODES
from safescale.taxonomy.labeling import gold as gold_file
from safescale.taxonomy.labeling.server import HOST, LabelingServer


def test_sample_is_deterministic_and_order_independent():
    ids = list(range(1, 1001))
    first = gold_file.sample_ids(ids, 50, seed=7)
    assert first == gold_file.sample_ids(list(reversed(ids)) + ids[:10], 50, seed=7)
    assert len(set(first)) == 50
    assert first != gold_file.sample_ids(ids, 50, seed=8)


def test_sample_larger_than_corpus_is_an_error():
    with pytest.raises(ValueError, match="exceeds"):
        gold_file.sample_ids([1, 2, 3], 5, seed=1)


def test_create_gold_set_from_db(fixture_recalls):
    gold = gold_file.create_gold_set(fixture_recalls, n=5, seed=3)
    assert len(gold.items) == 5
    assert all(item.title and item.url and not item.labels for item in gold.items)
    assert [i.recall_id for i in gold.items] == [
        i.recall_id for i in gold_file.create_gold_set(fixture_recalls, n=5, seed=3).items
    ]


def _gold() -> gold_file.GoldSet:
    items = [
        gold_file.GoldItem(10, "Heater recall", "posing a fire hazard", None, "https://x/10", None),
        gold_file.GoldItem(20, "Crib recall", None, "Entrapment.", "https://x/20", "2010-01-01"),
    ]
    return gold_file.GoldSet(seed=1, items=items, created_at="2026-10-19T00:00:00+00:00")


def test_apply_label_validates_and_orders():
    gold = _gold()
    item = gold_file.apply_label(
        gold, 10, labels=["burn", "fire_overheating"], violates_standard=True, notes=" hot "
    )
    assert item.labels == ["fire_overheating", "burn"]  # canonical category order
    assert item.notes == "hot" and item.violates_standard and item.labeled_at
    with pytest.raises(ValueError, match="unknown"):
        gold_file.apply_label(gold, 10, labels=["lava"], violates_standard=False, notes="")
    with pytest.raises(ValueError, match="other"):
        gold_file.apply_label(gold, 10, labels=["other", "burn"], violates_standard=False, notes="")
    with pytest.raises(KeyError):
        gold_file.apply_label(gold, 99, labels=["burn"], violates_standard=False, notes="")


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "nested" / "gold.json"
    gold = _gold()
    gold_file.apply_label(gold, 20, labels=["entrapment"], violates_standard=False, notes="")
    gold_file.save_gold(gold, path)
    loaded = gold_file.load_gold(path)
    assert loaded == gold
    assert not path.with_suffix(".json.tmp").exists()


@pytest.fixture
def server(tmp_path):
    srv = LabelingServer(_gold(), tmp_path / "gold.json", port=0)
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _request(srv, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection(HOST, srv.server_port, timeout=5)
    data = json.dumps(body) if body is not None else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    hdrs.update(headers or {})
    conn.request(method, path, body=data, headers=hdrs)
    res = conn.getresponse()
    payload = res.read()
    conn.close()
    return res.status, payload


def test_server_binds_to_localhost_only(server):
    assert server.server_address[0] == "127.0.0.1"


def test_server_serves_page_and_gold(server):
    status, page = _request(server, "GET", "/")
    assert status == 200 and b"Hazard labeling" in page
    status, body = _request(server, "GET", "/api/gold")
    data = json.loads(body)
    assert [c["code"] for c in data["categories"]] == list(CATEGORY_CODES)
    assert [i["recall_id"] for i in data["items"]] == [10, 20]


def test_put_saves_to_disk_and_resumes(server):
    body = {"labels": ["fire_overheating"], "violates_standard": True, "notes": "n"}
    status, payload = _request(server, "PUT", "/api/items/10", body)
    assert status == 200 and json.loads(payload)["labels"] == ["fire_overheating"]
    reloaded = gold_file.load_gold(server.gold_path)
    assert reloaded.item(10).labels == ["fire_overheating"] and reloaded.item(10).violates_standard


@pytest.mark.parametrize(
    ("path", "body", "headers", "expected"),
    [
        ("/api/items/10", {"labels": ["lava"]}, None, 400),
        ("/api/items/99", {"labels": ["burn"]}, None, 404),
        ("/api/items/abc", {"labels": ["burn"]}, None, 404),
        ("/api/items/10", {"labels": "burn"}, None, 400),
        ("/api/items/10", {"labels": ["burn"]}, {"Content-Type": "text/plain"}, 415),
        ("/api/items/10", {"labels": ["burn"]}, {"Host": "evil.example:80"}, 403),
    ],
)
def test_put_rejects_bad_requests(server, path, body, headers, expected):
    status, _ = _request(server, "PUT", path, body, headers)
    assert status == expected
    assert not server.gold_path.exists()


def test_get_rejects_foreign_host(server):
    status, _ = _request(server, "GET", "/api/gold", headers={"Host": "evil.example"})
    assert status == 403
