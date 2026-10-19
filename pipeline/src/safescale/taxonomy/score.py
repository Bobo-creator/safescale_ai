"""`safescale score-hazards`: the classifier against the human gold labels (P / R / F1)."""

from dataclasses import dataclass

from safescale.taxonomy.categories import CATEGORY_CODES
from safescale.taxonomy.classify import classify
from safescale.taxonomy.labeling.gold import GoldSet


@dataclass(frozen=True)
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None:
            return None
        return 2 * p * r / (p + r) if p + r else 0.0

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)


@dataclass(frozen=True)
class Mismatch:
    recall_id: int
    missed: list[str]  # in gold, not predicted
    extra: list[str]  # predicted, not in gold


@dataclass(frozen=True)
class Score:
    scored: int  # labeled items
    skipped: int  # items not labeled yet
    per_category: dict[str, Counts]
    micro: Counts
    exact_match: int  # items whose predicted set equals the gold set
    violation: Counts  # "violates a standard" flag
    mismatches: list[Mismatch]


def score(gold: GoldSet) -> Score:
    per_category = {code: Counts() for code in CATEGORY_CODES}
    violation = Counts()
    exact = 0
    mismatches = []
    labeled = [item for item in gold.items if item.is_labeled]
    for item in labeled:
        result = classify(
            title=item.title, hazard_text=item.hazard_text, description=item.description
        )
        predicted, truth = set(result.categories), set(item.labels)
        for code in CATEGORY_CODES:
            hit = Counts(
                tp=int(code in predicted and code in truth),
                fp=int(code in predicted and code not in truth),
                fn=int(code not in predicted and code in truth),
            )
            per_category[code] = per_category[code] + hit
        flagged = bool(result.violations)
        violation = violation + Counts(
            tp=int(flagged and item.violates_standard),
            fp=int(flagged and not item.violates_standard),
            fn=int(not flagged and item.violates_standard),
        )
        if predicted == truth:
            exact += 1
        else:
            mismatches.append(
                Mismatch(
                    item.recall_id,
                    missed=[c for c in CATEGORY_CODES if c in truth - predicted],
                    extra=[c for c in CATEGORY_CODES if c in predicted - truth],
                )
            )
    micro = sum(per_category.values(), Counts())
    return Score(
        scored=len(labeled),
        skipped=len(gold.items) - len(labeled),
        per_category=per_category,
        micro=micro,
        exact_match=exact,
        violation=violation,
        mismatches=mismatches,
    )


def format_score(s: Score) -> str:
    def pct(x: float | None) -> str:
        return "   –" if x is None else f"{x:4.2f}"

    lines = [
        f"scored {s.scored} labeled recalls ({s.skipped} not labeled yet)",
        "",
        f"{'category':<26} {'gold':>4} {'pred':>4} {'tp':>3}  {'P':>4}  {'R':>4}  {'F1':>4}",
    ]
    for code, c in s.per_category.items():
        lines.append(
            f"{code:<26} {c.tp + c.fn:>4} {c.tp + c.fp:>4} {c.tp:>3}  "
            f"{pct(c.precision)}  {pct(c.recall)}  {pct(c.f1)}"
        )
    m, v = s.micro, s.violation
    lines += [
        f"{'micro (all labels)':<26} {m.tp + m.fn:>4} {m.tp + m.fp:>4} {m.tp:>3}  "
        f"{pct(m.precision)}  {pct(m.recall)}  {pct(m.f1)}",
        "",
        f"exact match (whole label set): {s.exact_match}/{s.scored}",
        f"violates-a-standard flag: P {pct(v.precision)}  R {pct(v.recall)}  F1 {pct(v.f1)}"
        f"  (gold {v.tp + v.fn}, predicted {v.tp + v.fp})",
    ]
    if s.mismatches:
        lines += ["", "mismatches (recall id: missed / extra):"]
        for mm in s.mismatches:
            lines.append(
                f"  {mm.recall_id}: missed {', '.join(mm.missed) or '-'} / "
                f"extra {', '.join(mm.extra) or '-'}"
            )
    return "\n".join(lines)
