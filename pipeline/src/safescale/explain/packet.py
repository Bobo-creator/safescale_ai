"""The evidence packet: everything the model may use, built deterministically from the report."""

import json
from dataclasses import dataclass

import psycopg

from safescale.analysis.report import HazardReport
from safescale.explain.validate import Grounding, numbers_in

MAX_MATCHES = 15
MAX_HAZARD_CHARS = 400
MAX_DESCRIPTION_CHARS = 300
_ID_KEYS = {"recall_id", "recall_ids"}


@dataclass(frozen=True)
class Packet:
    data: dict  # sent to the model as JSON
    grounding: Grounding


def truncate(text: str | None, limit: int) -> str | None:
    if not text or len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"


def build_packet(conn: psycopg.Connection, report: HazardReport) -> Packet:
    matches = sorted((m for m in report.matches if m.relevant), key=lambda m: m.rank)[:MAX_MATCHES]
    ids = [m.recall_id for m in matches]
    in_packet = set(ids)
    extra = {
        rid: (products or [], description)
        for rid, products, description in conn.execute(
            "select recall_id, product_names, description from recalls where recall_id = any(%s)",
            (ids,),
        )
    }

    def cited(recall_ids: list[int]) -> list[int]:
        return [rid for rid in recall_ids if rid in in_packet]

    data = {
        "product_description": report.query,
        "overall_signal": report.overall_signal,
        "signal_drivers": report.signal_drivers,
        "similar_recalls_considered": len(report.matches),
        "relevant_similar_recalls": report.relevant,
        "hazard_profile": [
            {
                "category": s.code,
                "label": s.label,
                "similar_recalls": s.count,
                "share_percent": round(100 * s.share),
                "times_its_rate_among_all_recalls": round(s.lift, 1),
                "signal": s.signal,
                "recall_ids": cited(s.recall_ids),
            }
            for s in report.profile
        ],
        "shared_terms": [
            {"term": t.term, "similar_recalls": t.matches} for t in report.shared_terms
        ],
        "failure_terms": [
            {"term": t.term, "similar_recalls": t.matches} for t in report.failure_terms
        ],
        "investigation_areas": [
            {
                "area_id": a.id,
                "title": a.title,
                "supporting_recalls": a.support,
                "trigger_terms": a.terms,
                "recall_ids": cited(a.recall_ids),
            }
            for a in report.investigation_areas
        ],
        "standards_cited_by_similar_recalls": [
            {"standard": s.standard, "similar_recalls": s.count} for s in report.standards
        ],
        "recalls": [
            {
                "recall_id": m.recall_id,
                "date": m.recall_date.isoformat() if m.recall_date else None,
                "title": m.title,
                "products": extra.get(m.recall_id, ([], None))[0],
                "hazard": truncate(m.hazard_text, MAX_HAZARD_CHARS),
                "description": truncate(
                    extra.get(m.recall_id, ([], None))[1], MAX_DESCRIPTION_CHARS
                ),
                "hazard_categories": [lbl.category for lbl in m.labels],
            }
            for m in matches
        ],
    }
    grounding = Grounding(
        match_ids=in_packet,
        category_ids={s.code: set(cited(s.recall_ids)) for s in report.profile},
        area_ids={a.id: set(cited(a.recall_ids)) for a in report.investigation_areas},
        numbers=numbers_in(json.dumps(_without_ids(data), ensure_ascii=False)),
    )
    return Packet(data=data, grounding=grounding)


def _without_ids(value):
    """The packet minus recall ids, so an id can't pass as a statistic in the number check."""
    if isinstance(value, dict):
        return {k: _without_ids(v) for k, v in value.items() if k not in _ID_KEYS}
    if isinstance(value, list):
        return [_without_ids(v) for v in value]
    return value
