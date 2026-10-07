import hashlib
import json
from pathlib import Path

import httpx
import pytest

from safescale.ingest import run_ingest
from safescale.ingest.fetch import CPSC_RECALLS_URL, fetch_snapshot, read_snapshot

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "recalls_sample.json"
FIXTURE_BYTES = FIXTURE_PATH.read_bytes()


def mock_client(body: bytes = FIXTURE_BYTES, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(CPSC_RECALLS_URL)
        assert request.url.params["format"] == "json"
        return httpx.Response(status, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def offline_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network call to {request.url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_writes_snapshot_with_matching_hash(tmp_path):
    path = fetch_snapshot(mock_client(), tmp_path)
    assert path.parent == tmp_path and path.name.startswith("recalls_")
    records, sha256 = read_snapshot(path)
    assert len(records) == len(json.loads(FIXTURE_BYTES))
    assert sha256 == hashlib.sha256(FIXTURE_BYTES).hexdigest()


def test_fetch_raises_on_http_error(tmp_path):
    with pytest.raises(httpx.HTTPStatusError):
        fetch_snapshot(mock_client(b"oops", status=503), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_fetch_rejects_non_list_json(tmp_path):
    with pytest.raises(ValueError, match="not a list"):
        fetch_snapshot(mock_client(b'{"error": "x"}'), tmp_path)


def test_ingest_from_api_records_source_and_snapshot(migrated_conn, tmp_path):
    summary = run_ingest(migrated_conn, client=mock_client(), raw_dir=tmp_path)
    assert summary.snapshot.parent == tmp_path
    assert summary.result.inserted == summary.fetched
    source = migrated_conn.execute("select source from ingest_runs").fetchone()[0]
    assert source == "api"


def test_ingest_from_snapshot_makes_no_network_call(migrated_conn):
    summary = run_ingest(migrated_conn, snapshot=FIXTURE_PATH, client=offline_client())
    assert summary.result.inserted == summary.fetched > 0


def test_ingest_limit_loads_exactly_n(migrated_conn):
    summary = run_ingest(migrated_conn, snapshot=FIXTURE_PATH, limit=5)
    assert summary.fetched == 5
    assert migrated_conn.execute("select count(*) from recalls").fetchone()[0] == 5


def test_rejected_records_are_counted_and_logged(migrated_conn, tmp_path, caplog):
    records = json.loads(FIXTURE_BYTES)
    records[0]["RecallDate"] = "not a date"
    snapshot = tmp_path / "bad.json"
    snapshot.write_text(json.dumps(records))

    summary = run_ingest(migrated_conn, snapshot=snapshot)

    assert summary.rejected == 1
    assert summary.result.inserted == len(records) - 1
    assert f"RecallID={records[0]['RecallID']}" in caplog.text
    rejected = migrated_conn.execute("select rejected from ingest_runs").fetchone()[0]
    assert rejected == 1
