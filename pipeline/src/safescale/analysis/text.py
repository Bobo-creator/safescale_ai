"""Plain-text rendering of a HazardReport for the terminal."""

from safescale.analysis.report import HazardReport
from safescale.taxonomy.categories import CATEGORIES

_LABELS = {c.code: c.label for c in CATEGORIES}
MAX_MATCHES_SHOWN = 10


def format_report(report: HazardReport) -> str:
    r = report
    drivers = ", ".join(_LABELS[c] for c in r.signal_drivers)
    lines = [
        f"Historical signal: {r.overall_signal}" + (f" ({drivers})" if drivers else ""),
        f"Based on {r.relevant} relevant of {len(r.matches)} similar recalls "
        f"(method {r.method}, similarity >= {r.relevance_floor:.2f}).",
    ]
    if r.insufficient_evidence:
        lines.append(
            "Few similar recalls exist, so there is not enough historical evidence for a signal. "
            "This does not mean the product has no hazards."
        )
    if r.profile:
        lines += ["", "Hazard profile (share of relevant similar recalls; x = vs all recalls)"]
        for s in r.profile:
            lines.append(
                f"  {s.signal:<9}{s.label:<30}{s.count:>3}/{r.relevant:<3} {s.share:>4.0%}"
                f"  {s.lift:>4.1f}x"
            )
    if r.shared_terms:
        lines += ["", "Shared with your description: " + _terms(r.shared_terms)]
    if r.failure_terms:
        lines += ["Recurring failure terms: " + _terms(r.failure_terms)]
    if r.investigation_areas:
        lines += ["", "Areas to consider investigating (recommendations for review)"]
        for i, area in enumerate(r.investigation_areas, 1):
            found = f"; {', '.join(area.terms)}" if area.terms else ""
            lines.append(f"  {i}. {area.title} ({area.support} similar recalls{found})")
            lines += [f"       - {check}" for check in area.checks]
    if r.standards:
        lines += ["", "Standards that similar recalls failed (review whether they apply)"]
        lines += [f"  {s.standard}: {s.count} similar recalls" for s in r.standards]
    lines += ["", f"Top matches (of {len(r.matches)})"]
    for m in r.matches[:MAX_MATCHES_SHOWN]:
        weak = "" if m.relevant else "  [weak match]"
        cats = ", ".join(lbl.category for lbl in m.labels) or "unlabeled"
        lines.append(f"  {m.rank:>3}. [{m.cosine:.3f}] {m.recall_date}  {m.title}{weak}")
        lines.append(f"       {cats} · {m.url}")
    lines += ["", r.disclaimer]
    return "\n".join(lines)


def _terms(terms) -> str:
    return ", ".join(f"{t.term} ({t.matches})" for t in terms)
