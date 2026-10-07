"""data-ingest: CPSC recalls -> cleaned rows in Postgres."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg
from pydantic import ValidationError

from safescale import config
from safescale.ingest.clean import CleanRecall, to_clean_recall
from safescale.ingest.fetch import fetch_snapshot, read_snapshot
from safescale.ingest.load import LoadResult, load_recalls, record_run

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestSummary:
    run_id: int
    snapshot: Path
    fetched: int
    rejected: int
    result: LoadResult


def run_ingest(
    conn: psycopg.Connection,
    *,
    snapshot: Path | None = None,
    limit: int | None = None,
    client: httpx.Client | None = None,
    raw_dir: Path = config.RAW_DATA_DIR,
) -> IngestSummary:
    """Fetch (or read a saved snapshot), clean, and load recalls; audit the run."""
    started_at = datetime.now(UTC)
    source = "snapshot" if snapshot else "api"
    if snapshot is None:
        with client or httpx.Client() as http:
            snapshot = fetch_snapshot(http, raw_dir)

    records, sha256 = read_snapshot(snapshot)
    if limit is not None:
        records = records[:limit]

    cleaned: list[CleanRecall] = []
    rejected = 0
    for record in records:
        try:
            cleaned.append(to_clean_recall(record))
        except (ValidationError, ValueError) as exc:
            rejected += 1
            log.warning("rejected RecallID=%s: %s", record.get("RecallID"), exc)

    with conn.transaction():
        result = load_recalls(conn, cleaned)
        run_id = record_run(
            conn,
            started_at=started_at,
            source=source,
            snapshot_sha256=sha256,
            fetched=len(records),
            rejected=rejected,
            result=result,
        )
    return IngestSummary(run_id, snapshot, len(records), rejected, result)
