import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from safescale.ingest.clean import to_clean_recall
from safescale.ingest.load import LoadResult, load_recalls, record_run

FIXTURES = json.loads((Path(__file__).parents[1] / "fixtures" / "recalls_sample.json").read_text())


def clean_all(records=FIXTURES):
    return [to_clean_recall(record) for record in records]


def test_fresh_load_inserts_everything(migrated_conn):
    result = load_recalls(migrated_conn, clean_all())
    assert result == LoadResult(inserted=len(FIXTURES), updated=0, unchanged=0)
    count = migrated_conn.execute("select count(*) from recalls").fetchone()[0]
    assert count == len(FIXTURES)


def test_reload_is_a_no_op(migrated_conn):
    load_recalls(migrated_conn, clean_all())
    before = dict(migrated_conn.execute("select recall_id, updated_at from recalls").fetchall())
    result = load_recalls(migrated_conn, clean_all())
    assert result == LoadResult(inserted=0, updated=0, unchanged=len(FIXTURES))
    after = dict(migrated_conn.execute("select recall_id, updated_at from recalls").fetchall())
    assert after == before


def test_changed_record_updates_only_that_row(migrated_conn):
    load_recalls(migrated_conn, clean_all())
    before = dict(migrated_conn.execute("select recall_id, updated_at from recalls").fetchall())

    records = copy.deepcopy(FIXTURES)
    target = records[0]
    target["Remedies"] = [{"Name": "Contact the firm for a free repair kit."}]  # outside document
    result = load_recalls(migrated_conn, clean_all(records))

    assert result == LoadResult(inserted=0, updated=1, unchanged=len(FIXTURES) - 1)
    after = dict(migrated_conn.execute("select recall_id, updated_at from recalls").fetchall())
    changed = {rid for rid in after if after[rid] != before[rid]}
    assert changed == {target["RecallID"]}
    remedy = migrated_conn.execute(
        "select remedy_text from recalls where recall_id = %s", (target["RecallID"],)
    ).fetchone()[0]
    assert remedy == "Contact the firm for a free repair kit."


def test_stored_row_round_trips(migrated_conn):
    recall = clean_all()[0]
    load_recalls(migrated_conn, [recall])
    row = migrated_conn.execute(
        "select raw, product_names, document <> '', length(content_hash) from recalls"
    ).fetchone()
    assert row == (recall.raw, recall.product_names, True, 64)


def test_duplicate_ids_in_one_batch_keep_the_last(migrated_conn):
    first, second = copy.deepcopy(FIXTURES[0]), copy.deepcopy(FIXTURES[0])
    second["Title"] = "Second copy wins"
    result = load_recalls(migrated_conn, clean_all([first, second]))
    assert result.inserted == 1
    title = migrated_conn.execute("select title from recalls").fetchone()[0]
    assert title == "Second copy wins"


def test_record_run_writes_audit_row(migrated_conn):
    started = datetime(2026, 10, 6, tzinfo=UTC)
    run_id = record_run(
        migrated_conn,
        started_at=started,
        source="snapshot",
        snapshot_sha256="ab" * 32,
        fetched=20,
        rejected=2,
        result=LoadResult(inserted=10, updated=3, unchanged=5),
    )
    row = migrated_conn.execute(
        "select source, fetched, inserted, updated, unchanged, rejected, finished_at is not null "
        "from ingest_runs where run_id = %s",
        (run_id,),
    ).fetchone()
    assert row == ("snapshot", 20, 10, 3, 5, 2, True)
