"""explain(): evidence packet -> model draft -> validation -> (retry | fallback) -> Explanation."""

import logging
from dataclasses import asdict, dataclass, field

import psycopg

from safescale.analysis.report import DISCLAIMER, HazardReport
from safescale.explain.explainer import Explainer, ExplainerError, Usage
from safescale.explain.packet import Packet, build_packet
from safescale.explain.prompt import PROMPT_VERSION
from safescale.explain.schema import (
    ExplanationDraft,
    HazardParagraph,
    InvestigationNote,
    MatchReason,
    Sentence,
)
from safescale.explain.validate import Dropped, validate

log = logging.getLogger(__name__)

CAVEAT = (
    "Recall data only contains products that had problems, so these shares describe what went "
    "wrong in similar recalled products. They are not the chance that a new product has the hazard."
)
INSUFFICIENT_NOTICE = (
    "Few similar recalls exist for this description, so there is not enough historical evidence "
    "to explain. This does not mean the product has no hazards."
)
FALLBACK_CITATIONS = 3


@dataclass(frozen=True)
class Validation:
    first_try_clean: bool = True  # the first draft passed with nothing dropped
    retries: int = 0
    fallback_used: bool = False
    dropped: list[Dropped] = field(default_factory=list)
    error: str | None = None  # the model failed; the explanation is deterministic


@dataclass(frozen=True)
class Explanation:
    summary: list[Sentence]
    hazards: list[HazardParagraph]
    match_reasons: list[MatchReason]
    investigation_notes: list[InvestigationNote]
    notice: str | None  # set instead of an explanation when evidence is insufficient
    generated: bool  # False = deterministic text only
    model: str | None
    prompt_version: int
    usage: Usage
    validation: Validation
    caveat: str = CAVEAT
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        def dump(items):
            return [item.model_dump() for item in items]

        return {
            "summary": dump(self.summary),
            "hazards": dump(self.hazards),
            "match_reasons": dump(self.match_reasons),
            "investigation_notes": dump(self.investigation_notes),
            "notice": self.notice,
            "generated": self.generated,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "usage": asdict(self.usage),
            "validation": asdict(self.validation),
            "caveat": self.caveat,
            "disclaimer": self.disclaimer,
        }


def explain(conn: psycopg.Connection, report: HazardReport, *, explainer: Explainer) -> Explanation:
    if report.insufficient_evidence:
        return Explanation(
            [], [], [], [], INSUFFICIENT_NOTICE, False, None, PROMPT_VERSION, Usage(), Validation()
        )

    packet = build_packet(conn, report)
    usage, dropped, retries = Usage(), [], 0
    try:
        draft, used = explainer.draft(packet.data)
        usage += used
        result = validate(draft, packet.grounding)
        first_try_clean = not result.dropped
        dropped += result.dropped
        if result.needs_retry:
            retries = 1
            log.info("retrying explanation: %d item(s) dropped", len(result.dropped))
            draft, used = explainer.draft(packet.data, feedback=result.feedback())
            usage += used
            result = validate(draft, packet.grounding)
            dropped += result.dropped
    except ExplainerError as exc:
        log.warning("explainer failed: %s", exc)
        return _fallback_only(report, packet, explainer.model, usage, retries, dropped, str(exc))

    kept = result.draft
    fallback_used = result.needs_retry
    summary = _fallback_summary(report, packet) if fallback_used else kept.summary
    return Explanation(
        summary=summary,
        hazards=kept.hazards,
        match_reasons=kept.match_reasons,
        investigation_notes=kept.investigation_notes,
        notice=None,
        generated=bool(
            kept.summary or kept.hazards or kept.match_reasons or kept.investigation_notes
        ),
        model=explainer.model,
        prompt_version=PROMPT_VERSION,
        usage=usage,
        validation=Validation(first_try_clean, retries, fallback_used, dropped),
    )


def _fallback_only(report, packet, model, usage, retries, dropped, error) -> Explanation:
    return Explanation(
        summary=_fallback_summary(report, packet),
        hazards=[],
        match_reasons=[],
        investigation_notes=[],
        notice=None,
        generated=False,
        model=model,
        prompt_version=PROMPT_VERSION,
        usage=usage,
        validation=Validation(False, retries, True, dropped, error),
    )


def _fallback_summary(report: HazardReport, packet: Packet) -> list[Sentence]:
    """Deterministic sentences from the report itself (grounded by construction)."""
    sentences = []
    for stat in report.profile:
        if stat.code == "other" or stat.signal == "LOW" or len(sentences) == 2:
            continue
        ids = sorted(packet.grounding.category_ids.get(stat.code, set()))[:FALLBACK_CITATIONS]
        if not ids:
            continue
        sentences.append(
            Sentence(
                text=f"{stat.count} of {report.relevant} similar recalls involved "
                f"{stat.label.lower()} ({round(100 * stat.share)}%, {stat.lift:.1f}× its rate "
                "among all recalls).",
                citations=ids,
            )
        )
    if not sentences:
        ids = sorted(packet.grounding.match_ids)[:FALLBACK_CITATIONS]
        sentences.append(
            Sentence(
                text=f"The {report.relevant} similar recalls show no dominant hazard category.",
                citations=ids,
            )
        )
    return sentences


__all__ = ["Explanation", "ExplanationDraft", "Validation", "explain"]
