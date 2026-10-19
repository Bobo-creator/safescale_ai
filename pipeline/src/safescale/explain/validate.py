"""Grounding validator: every shown sentence must be backed by the evidence packet.

Failing items are dropped (never shown) with a reason; explain() decides whether to retry.
"""

import re
from dataclasses import dataclass, field

from safescale.explain.schema import (
    ExplanationDraft,
    HazardParagraph,
    InvestigationNote,
    Sentence,
)

MAX_SUMMARY, MAX_HAZARD_SENTENCES, MAX_MATCH_REASONS = 4, 3, 8
RETRY_DROP_SHARE = 0.25  # retry when more than this share of items was dropped

BANNED = re.compile(
    r"\bsafe\b|\bunsafe\b|\bsafely\b|complian|\bcertif|guarante|\bwill fail\b|probabilit"
    r"|\blikely to fail\b|\brequired\b|\bmust\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# A trailing "[10158, 755]" or "(#61)" that repeats the sentence's own citations.
_TRAILING_IDS = re.compile(r"\s*[\[(]\s*#?\d+(?:\s*,\s*#?\d+)*\s*[\])]\s*\.?\s*$")


def normalize_number(raw: str) -> str:
    """'1,250' -> '1250', '1.90' -> '1.9', '56' -> '56'."""
    value = float(raw.replace(",", ""))
    return f"{value:g}"


def numbers_in(text: str) -> set[str]:
    return {normalize_number(m.group(0)) for m in _NUMBER.finditer(text)}


@dataclass(frozen=True)
class Grounding:
    """What the packet allows a sentence to rely on."""

    match_ids: set[int]  # relevant matches in the packet
    category_ids: dict[str, set[int]]  # category -> packet matches carrying it
    area_ids: dict[str, set[int]]  # investigation area -> packet matches supporting it
    numbers: set[str]  # every number that appears anywhere in the packet


@dataclass(frozen=True)
class Dropped:
    where: str  # e.g. "summary[1]", "hazards[fire_overheating][0]", "match_reasons[2]"
    reason: str
    text: str


@dataclass
class ValidationResult:
    draft: ExplanationDraft  # only the items that passed
    dropped: list[Dropped] = field(default_factory=list)
    total_items: int = 0

    @property
    def needs_retry(self) -> bool:
        if not self.draft.summary:
            return True
        return self.total_items > 0 and len(self.dropped) / self.total_items > RETRY_DROP_SHARE

    def feedback(self) -> list[str]:
        return [f"{d.where}: {d.reason}" for d in self.dropped]


def strip_repeated_citations(s: Sentence) -> Sentence:
    """Drop a trailing id list that only repeats the citations (a formatting habit, not a claim).
    A list naming other ids is left in place, so the number check still catches it."""
    match = _TRAILING_IDS.search(s.text)
    if not match:
        return s
    ids = {int(x) for x in re.findall(r"\d+", match.group(0))}
    if not ids <= set(s.citations):
        return s
    text = s.text[: match.start()].rstrip()
    if text and text[-1] not in ".!?":
        text += "."
    return Sentence(text=text, citations=s.citations)


def _text_problems(text: str, grounding: Grounding) -> list[str]:
    problems = []
    if match := BANNED.search(text):
        problems.append(f"uses non-advisory wording {match.group(0)!r}")
    invented = sorted(numbers_in(text) - grounding.numbers)
    if invented:
        problems.append(f"numbers not in the evidence: {', '.join(invented)}")
    return problems


def _sentence_problems(s: Sentence, grounding: Grounding, allowed: set[int] | None) -> list[str]:
    problems = []
    if not s.text.strip():
        problems.append("empty sentence")
    if not s.citations:
        problems.append("no citation")
    unknown = sorted(set(s.citations) - grounding.match_ids)
    if unknown:
        problems.append(f"cites recalls that are not in the evidence: {unknown}")
    elif allowed is not None:
        off_topic = sorted(set(s.citations) - allowed)
        if off_topic:
            problems.append(f"cites recalls that don't support this claim: {off_topic}")
    return problems + _text_problems(s.text, grounding)


def validate(draft: ExplanationDraft, grounding: Grounding) -> ValidationResult:
    draft = _normalized(draft)
    dropped: list[Dropped] = []
    total = 0

    def check(where: str, text: str, problems: list[str]) -> bool:
        if problems:
            dropped.append(Dropped(where, "; ".join(problems), text))
        return not problems

    summary = []
    for i, s in enumerate(draft.summary):
        total += 1
        if i >= MAX_SUMMARY:
            check(f"summary[{i}]", s.text, [f"more than {MAX_SUMMARY} summary sentences"])
        elif check(f"summary[{i}]", s.text, _sentence_problems(s, grounding, None)):
            summary.append(s)

    hazards, seen_categories = [], set()
    for paragraph in draft.hazards:
        code = paragraph.category
        where = f"hazards[{code}]"
        if code in seen_categories or code not in grounding.category_ids:
            total += 1
            reason = "duplicate category" if code in seen_categories else "category not in report"
            check(where, " ".join(s.text for s in paragraph.sentences), [reason])
            continue
        seen_categories.add(code)
        kept = []
        for i, s in enumerate(paragraph.sentences):
            total += 1
            if i >= MAX_HAZARD_SENTENCES:
                check(f"{where}[{i}]", s.text, [f"more than {MAX_HAZARD_SENTENCES} sentences"])
            elif check(
                f"{where}[{i}]",
                s.text,
                _sentence_problems(s, grounding, grounding.category_ids[code]),
            ):
                kept.append(s)
        if kept:
            hazards.append(HazardParagraph(category=code, sentences=kept))

    reasons, seen_matches = [], set()
    for i, reason in enumerate(draft.match_reasons):
        total += 1
        text = "; ".join(reason.shared + reason.different)
        problems = []
        if i >= MAX_MATCH_REASONS:
            problems.append(f"more than {MAX_MATCH_REASONS} match reasons")
        if reason.recall_id not in grounding.match_ids:
            problems.append(f"recall {reason.recall_id} is not in the evidence")
        if reason.recall_id in seen_matches:
            problems.append("duplicate recall")
        if not reason.shared:
            problems.append("no shared features")
        problems += _text_problems(text, grounding)
        if check(f"match_reasons[{i}]", text, problems):
            reasons.append(reason)
            seen_matches.add(reason.recall_id)

    notes, seen_areas = [], set()
    for note in draft.investigation_notes:
        total += 1
        where = f"investigation_notes[{note.area_id}]"
        if note.area_id not in grounding.area_ids:
            check(where, note.sentence.text, ["area not in report"])
        elif note.area_id in seen_areas:
            check(where, note.sentence.text, ["duplicate area"])
        elif check(
            where,
            note.sentence.text,
            _sentence_problems(note.sentence, grounding, grounding.area_ids[note.area_id]),
        ):
            notes.append(InvestigationNote(area_id=note.area_id, sentence=note.sentence))
            seen_areas.add(note.area_id)

    kept = ExplanationDraft(
        summary=summary, hazards=hazards, match_reasons=reasons, investigation_notes=notes
    )
    return ValidationResult(draft=kept, dropped=dropped, total_items=total)


def _normalized(draft: ExplanationDraft) -> ExplanationDraft:
    return ExplanationDraft(
        summary=[strip_repeated_citations(s) for s in draft.summary],
        hazards=[
            HazardParagraph(
                category=p.category, sentences=[strip_repeated_citations(s) for s in p.sentences]
            )
            for p in draft.hazards
        ],
        match_reasons=draft.match_reasons,
        investigation_notes=[
            InvestigationNote(area_id=n.area_id, sentence=strip_repeated_citations(n.sentence))
            for n in draft.investigation_notes
        ],
    )
