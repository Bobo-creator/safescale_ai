"""Write cleaned recalls to Postgres: bulk COPY into a staging table, then one upsert."""

import logging
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb

from safescale.ingest.clean import CleanRecall
from safescale.ingest.document import build_document, content_hash

log = logging.getLogger(__name__)

_COLUMNS = (
    "recall_id",
    "recall_number",
    "recall_date",
    "last_publish_date",
    "title",
    "description",
    "url",
    "product_names",
    "product_types",
    "hazard_text",
    "injuries_text",
    "remedy_text",
    "units_text",
    "manufacturer_countries",
    "document",
    "content_hash",
    "raw",
)
_COLUMN_LIST = ", ".join(_COLUMNS)
_UPDATE_SET = ", ".join(f"{c} = excluded.{c}" for c in _COLUMNS if c != "recall_id")

# A row counts as changed when its original API record changed, not just its document, so edits
# to fields outside the document (e.g. remedies) are still picked up.
_UPSERT = f"""
insert into recalls ({_COLUMN_LIST})
select {_COLUMN_LIST} from staging_recalls
on conflict (recall_id) do update set {_UPDATE_SET}, updated_at = now()
where recalls.raw is distinct from excluded.raw
returning (xmax = 0) as inserted
"""


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int
    unchanged: int


def _row(recall: CleanRecall) -> tuple:
    document = build_document(recall)
    return (
        recall.recall_id,
        recall.recall_number,
        recall.recall_date,
        recall.last_publish_date,
        recall.title,
        recall.description,
        recall.url,
        recall.product_names,
        recall.product_types,
        recall.hazard_text,
        recall.injuries_text,
        recall.remedy_text,
        recall.units_text,
        recall.manufacturer_countries,
        document,
        content_hash(document),
        Jsonb(recall.raw),
    )


def load_recalls(conn: psycopg.Connection, recalls: list[CleanRecall]) -> LoadResult:
    """Upsert recalls in one transaction and report what changed."""
    unique = {recall.recall_id: recall for recall in recalls}  # last occurrence wins
    if len(unique) < len(recalls):
        log.warning("dropped %d duplicate recall ids in batch", len(recalls) - len(unique))

    with conn.transaction():
        conn.execute(
            "create temp table staging_recalls (like recalls including defaults) on commit drop"
        )
        with conn.cursor() as cur:
            with cur.copy(f"copy staging_recalls ({_COLUMN_LIST}) from stdin") as copy:
                for recall in unique.values():
                    copy.write_row(_row(recall))
            flags = [row[0] for row in cur.execute(_UPSERT).fetchall()]

    inserted = sum(flags)
    updated = len(flags) - inserted
    return LoadResult(inserted=inserted, updated=updated, unchanged=len(unique) - len(flags))


def record_run(
    conn: psycopg.Connection,
    *,
    started_at: datetime,
    source: str,
    snapshot_sha256: str,
    fetched: int,
    rejected: int,
    result: LoadResult,
) -> int:
    """Insert one ingest_runs audit row and return its run_id."""
    row = conn.execute(
        """
        insert into ingest_runs (started_at, finished_at, source, snapshot_sha256,
                                 fetched, inserted, updated, unchanged, rejected)
        values (%s, now(), %s, %s, %s, %s, %s, %s, %s)
        returning run_id
        """,
        (
            started_at,
            source,
            snapshot_sha256,
            fetched,
            result.inserted,
            result.updated,
            result.unchanged,
            rejected,
        ),
    ).fetchone()
    return row[0]
