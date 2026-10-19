"""Hazard profile over the relevant matches, and the LOW / MODERATE / HIGH signals."""

from safescale.analysis.report import (
    HIGH_COUNT,
    HIGH_LIFT,
    HIGH_SHARE,
    MIN_RELEVANT,
    MODERATE_COUNT,
    MODERATE_SHARE,
    SIGNAL_ORDER,
    CategoryStat,
    Match,
    Signal,
)
from safescale.taxonomy.categories import CATEGORIES


def category_signal(count: int, share: float, lift: float) -> Signal:
    if share >= HIGH_SHARE and count >= HIGH_COUNT and lift >= HIGH_LIFT:
        return "HIGH"
    if share >= MODERATE_SHARE and count >= MODERATE_COUNT:
        return "MODERATE"
    return "LOW"


def build_profile(matches: list[Match], base_rates: dict[str, float]) -> list[CategoryStat]:
    """One row per category present among the relevant matches; strongest signal first."""
    relevant = [m for m in matches if m.relevant]
    stats = []
    for info in CATEGORIES:
        ids = [m.recall_id for m in relevant if info.code in {lbl.category for lbl in m.labels}]
        if not ids:
            continue
        share = len(ids) / len(relevant)
        base = base_rates.get(info.code, 0.0)
        lift = share / base if base else 0.0  # every category occurs in the corpus; JSON-safe
        stats.append(
            CategoryStat(
                code=info.code,
                label=info.label,
                count=len(ids),
                share=share,
                base_rate=base,
                lift=lift,
                signal=category_signal(len(ids), share, lift),
                recall_ids=ids,
            )
        )
    order = {info.code: i for i, info in enumerate(CATEGORIES)}
    return sorted(stats, key=lambda s: (-SIGNAL_ORDER[s.signal], -s.count, order[s.code]))


def overall_signal(profile: list[CategoryStat], relevant: int) -> tuple[Signal, list[str], bool]:
    """(signal, the categories that set it, insufficient_evidence). 'other' never drives it."""
    if relevant < MIN_RELEVANT:
        return "LOW", [], True
    candidates = [s for s in profile if s.code != "other"]
    if not candidates:
        return "LOW", [], False
    top = max(SIGNAL_ORDER[s.signal] for s in candidates)
    signal = next(s for s, rank in SIGNAL_ORDER.items() if rank == top)
    drivers = [s.code for s in candidates if SIGNAL_ORDER[s.signal] == top] if top else []
    return signal, drivers, False
