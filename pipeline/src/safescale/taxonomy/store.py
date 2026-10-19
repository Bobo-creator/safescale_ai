"""`safescale classify`: (re)label every recall; and reading labels back for given recalls."""

import logging
from collections import Counter
from dataclasses import dataclass

import psycopg

from safescale.taxonomy.classify import Classification, HazardLabel, StandardViolation, classify
from safescale.taxonomy.rules import TAXONOMY_VERSION

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassifyResult:
    recalls: int
    labels: int
    violations: int
    by_category: dict[str, int]  # recalls per category
    other_only: int  # recalls whose only label is 'other'
    flagged: int  # recalls with at least one standards violation


def classify_all(conn: psycopg.Connection) -> ClassifyResult:
    """Recompute every recall's labels and violations, replacing the old rows atomically.

    Readers keep seeing the previous rows until the transaction commits (delete, not truncate,
    so no exclusive lock blocks them meanwhile).
    """
    rows = conn.execute("select recall_id, title, hazard_text, description from recalls").fetchall()
    results = {
        recall_id: classify(title=title, hazard_text=hazard_text, description=description)
        for recall_id, title, hazard_text, description in rows
    }
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("delete from recall_hazards")
        cur.execute("delete from recall_standard_violations")
        with cur.copy(
            "copy recall_hazards (recall_id, category, evidence, source, taxonomy_version) "
            "from stdin"
        ) as copy:
            for recall_id, result in results.items():
                for label in result.labels:
                    copy.write_row(
                        (recall_id, label.category, label.evidence, label.source, TAXONOMY_VERSION)
                    )
        with cur.copy(
            "copy recall_standard_violations "
            "(recall_id, standard, evidence, source, taxonomy_version) from stdin"
        ) as copy:
            for recall_id, result in results.items():
                for v in result.violations:
                    copy.write_row((recall_id, v.standard, v.evidence, v.source, TAXONOMY_VERSION))

    by_category = Counter(c for result in results.values() for c in result.categories)
    summary = ClassifyResult(
        recalls=len(results),
        labels=sum(len(r.labels) for r in results.values()),
        violations=sum(len(r.violations) for r in results.values()),
        by_category=dict(by_category.most_common()),
        other_only=sum(r.categories == ["other"] for r in results.values()),
        flagged=sum(bool(r.violations) for r in results.values()),
    )
    log.info("classified %d recalls (taxonomy v%d)", summary.recalls, TAXONOMY_VERSION)
    return summary


_LABELS_FOR = """
select ids.recall_id,
       coalesce((
         select json_agg(json_build_array(h.category, h.evidence, h.source) order by c.sort_order)
         from recall_hazards h join hazard_categories c on c.code = h.category
         where h.recall_id = ids.recall_id
       ), '[]'),
       coalesce((
         select json_agg(json_build_array(v.standard, v.evidence, v.source) order by v.id)
         from recall_standard_violations v
         where v.recall_id = ids.recall_id
       ), '[]')
from unnest(%s::bigint[]) as ids (recall_id)
"""


def labels_for(conn: psycopg.Connection, recall_ids: list[int]) -> dict[int, Classification]:
    """Stored labels and violations for the given recalls, in one query.

    Recalls that have not been classified (or don't exist) are left out of the result.
    """
    out: dict[int, Classification] = {}
    for recall_id, labels, violations in conn.execute(_LABELS_FOR, (list(set(recall_ids)),)):
        if not labels:
            continue
        out[recall_id] = Classification(
            labels=[HazardLabel(*label) for label in labels],
            violations=[StandardViolation(*v) for v in violations],
        )
    return out
