"""classify(): label one recall with hazard categories, each backed by a verbatim fragment."""

import re
from dataclasses import dataclass, field
from typing import Literal

from safescale.taxonomy.categories import CATEGORY_CODES, Category
from safescale.taxonomy.rules import (
    HAZARD_RULES,
    STANDARD_SKIP,
    STANDARD_TRIGGERS,
    standard_name,
)

Source = Literal["hazard", "title", "description"]
MAX_EVIDENCE = 160
# Sentence ends, but not after common abbreviations ("the U.S. standard", "Acme Inc. recalls").
_SENTENCE_END = re.compile(
    r"(?<=[.!?;])(?<!\bU\.S\.)(?<!\bInc\.)(?<!\bCo\.)(?<!\bNo\.)(?<!\bMfg\.)(?<!\bCorp\.)"
    r"(?<!\bLtd\.)(?<!\bSt\.)(?<!\bvs\.)\s+"
)


@dataclass(frozen=True)
class HazardLabel:
    category: Category
    evidence: str  # verbatim fragment of the source field, <= MAX_EVIDENCE chars
    source: Source


@dataclass(frozen=True)
class StandardViolation:
    standard: str | None  # e.g. "ASTM F2057"; None when the text names no standard
    evidence: str
    source: Source


@dataclass(frozen=True)
class Classification:
    labels: list[HazardLabel]  # always >= 1, in category order
    violations: list[StandardViolation] = field(default_factory=list)

    @property
    def categories(self) -> list[Category]:
        return [label.category for label in self.labels]


def classify(*, title: str, hazard_text: str | None, description: str | None) -> Classification:
    """Hazard text and title first; the description only if they name no hazard; else 'other'."""
    primary: list[tuple[Source, str]] = [("hazard", hazard_text or ""), ("title", title or "")]
    labels = _match_fields(primary)
    if not labels and description:
        labels = _match_fields([("description", description)])
    if not labels:
        source, text = next(((s, t) for s, t in primary if t.strip()), ("description", ""))
        text = text or description or ""
        labels = [HazardLabel("other", text[:MAX_EVIDENCE].strip() or "(no text)", source)]
    violations = _find_violations(primary)
    if not violations and description:
        violations = _find_violations([("description", description)])
    return Classification(labels=labels, violations=violations)


def _find_violations(fields: list[tuple[Source, str]]) -> list[StandardViolation]:
    """One violation per distinct named standard; one unnamed violation if none are named.

    Fields are tried in order and the first one with any violation wins: titles usually repeat
    the hazard text in other words, which would otherwise double-count the same standard.
    """
    named: dict[str, StandardViolation] = {}
    unnamed: StandardViolation | None = None
    for source, text in fields:
        if named or unnamed:
            break
        for sentence in _sentences(text):
            trigger = next((m for t in STANDARD_TRIGGERS if (m := t.search(sentence))), None)
            if not trigger or STANDARD_SKIP.search(sentence):
                continue
            name = standard_name(sentence)
            fragment = evidence(sentence, trigger)
            if name and name not in named:
                named[name] = StandardViolation(name, fragment, source)
            elif not name and unnamed is None:
                unnamed = StandardViolation(None, fragment, source)
    if named:
        return list(named.values())
    return [unnamed] if unnamed else []


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END.split(text) if s.strip()] if text else []


def _match_fields(fields: list[tuple[Source, str]]) -> list[HazardLabel]:
    found: dict[Category, HazardLabel] = {}
    for source, text in fields:
        if not text:
            continue
        for category, rule in HAZARD_RULES.items():
            if category in found:
                continue
            match = rule.first_match(text)
            if match:
                found[category] = HazardLabel(category, evidence(text, match), source)
    return [found[c] for c in CATEGORY_CODES if c in found]


def evidence(text: str, match: re.Match[str]) -> str:
    """The sentence around the match, trimmed to MAX_EVIDENCE chars; always a substring of text."""
    start = 0
    for boundary in _SENTENCE_END.finditer(text, 0, match.start()):
        start = boundary.end()
    end_match = _SENTENCE_END.search(text, match.end())
    end = end_match.start() if end_match else len(text)
    if end - start > MAX_EVIDENCE:
        # Keep the match roughly centered inside the window.
        room = MAX_EVIDENCE - (match.end() - match.start())
        start = max(start, match.start() - room // 2)
        end = min(end, start + MAX_EVIDENCE)
        start = max(0, min(start, end - MAX_EVIDENCE))
    return text[start:end].strip()
