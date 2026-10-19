"""The hazard report: its data model, constants and JSON form."""

import dataclasses
from dataclasses import dataclass
from datetime import date
from typing import Literal

from safescale.retrieval.search import Method
from safescale.taxonomy.classify import HazardLabel, StandardViolation

ANALYSIS_VERSION = 1

DISCLAIMER = (
    "SafeScale AI does not certify that a product is safe or compliant. It identifies historically "
    "supported hazard signals and evidence that engineers should investigate further."
)

# A match counts toward the profile only when its cosine similarity reaches this floor. Measured
# 2026-10-19: real product queries score 0.34-0.57 down to rank 100; an unrelated query <= 0.18.
RELEVANCE_FLOOR = 0.30

# Signal rule v1 (frozen before evaluation; changes need the project owner's approval).
MIN_RELEVANT = 5  # fewer relevant matches than this -> insufficient evidence
HIGH_SHARE, HIGH_COUNT, HIGH_LIFT = 0.40, 5, 1.5
MODERATE_SHARE, MODERATE_COUNT = 0.20, 3

Signal = Literal["LOW", "MODERATE", "HIGH"]
SIGNAL_ORDER: dict[Signal, int] = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


@dataclass(frozen=True)
class Match:
    recall_id: int
    rank: int
    score: float  # the retrieval method's own score
    cosine: float  # similarity to the query embedding, whatever the method
    title: str
    url: str
    recall_date: date
    labels: list[HazardLabel]
    violations: list[StandardViolation]
    relevant: bool  # cosine >= the relevance floor used for this report


@dataclass(frozen=True)
class CategoryStat:
    code: str
    label: str
    count: int  # relevant matches carrying this category
    share: float  # count / relevant matches
    base_rate: float  # share of all recalls carrying this category
    lift: float  # share / base_rate
    signal: Signal
    recall_ids: list[int]


@dataclass(frozen=True)
class Term:
    term: str  # as the user or the recalls wrote it, not the stem
    matches: int
    recall_ids: list[int]


@dataclass(frozen=True)
class Area:
    id: str
    title: str
    checks: list[str]
    support: int
    recall_ids: list[int]
    terms: list[str]  # trigger terms found in the supporting matches


@dataclass(frozen=True)
class StandardStat:
    standard: str
    count: int
    recall_ids: list[int]


@dataclass(frozen=True)
class HazardReport:
    query: str
    method: Method
    k: int
    matches: list[Match]
    relevant: int
    relevance_floor: float
    profile: list[CategoryStat]
    overall_signal: Signal
    signal_drivers: list[str]
    insufficient_evidence: bool
    shared_terms: list[Term]
    failure_terms: list[Term]
    investigation_areas: list[Area]
    standards: list[StandardStat]
    taxonomy_version: int
    analysis_version: int = ANALYSIS_VERSION
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        """JSON-ready (dates as ISO strings)."""
        data = dataclasses.asdict(self)
        for match, raw in zip(self.matches, data["matches"], strict=True):
            raw["recall_date"] = match.recall_date.isoformat() if match.recall_date else None
        return data
