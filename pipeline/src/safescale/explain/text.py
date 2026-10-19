"""Terminal rendering of an explanation: [#id] citations and a reference list."""

from safescale.analysis.report import HazardReport
from safescale.explain.explain import Explanation
from safescale.explain.schema import Sentence
from safescale.taxonomy.categories import CATEGORIES

_LABELS = {c.code: c.label for c in CATEGORIES}


def format_explanation(report: HazardReport, exp: Explanation) -> str:
    matches = {m.recall_id: m for m in report.matches}
    areas = {a.id: a.title for a in report.investigation_areas}
    cited: list[int] = []

    def cite(s: Sentence) -> str:
        for rid in s.citations:
            if rid not in cited:
                cited.append(rid)
        return f"{s.text} " + "".join(f"[#{rid}]" for rid in s.citations)

    drivers = ", ".join(_LABELS[c] for c in report.signal_drivers)
    lines = [
        f"Historical signal: {report.overall_signal}" + (f" ({drivers})" if drivers else ""),
        f"Based on {report.relevant} relevant of {len(report.matches)} similar recalls.",
    ]
    if exp.notice:
        lines += ["", exp.notice]
    if exp.summary:
        lines += ["", "Summary"] + [f"  {cite(s)}" for s in exp.summary]
    if exp.hazards:
        lines += ["", "Hazards"]
        for paragraph in exp.hazards:
            text = " ".join(cite(s) for s in paragraph.sentences)
            lines.append(f"  {_LABELS[paragraph.category]}: {text}")
    if exp.match_reasons:
        lines += ["", "Why these recalls match"]
        for reason in exp.match_reasons:
            if reason.recall_id not in cited:
                cited.append(reason.recall_id)
            title = matches[reason.recall_id].title if reason.recall_id in matches else ""
            lines.append(f"  [#{reason.recall_id}] {title}")
            lines.append(f"       shared: {', '.join(reason.shared)}")
            if reason.different:
                lines.append(f"       different: {', '.join(reason.different)}")
    if exp.investigation_notes:
        lines += ["", "Investigation notes (recommendations for review)"]
        for note in exp.investigation_notes:
            lines.append(f"  {areas.get(note.area_id, note.area_id)}: {cite(note.sentence)}")
    if cited:
        lines += ["", "References"]
        for rid in cited:
            m = matches.get(rid)
            if m:
                lines.append(f"  [#{rid}] {m.recall_date}  {m.title}")
                lines.append(f"          {m.url}")
    v, u = exp.validation, exp.usage
    status = []
    if exp.model:
        status.append(f"model {exp.model}")
    if u.input_tokens:
        status.append(f"{u.input_tokens + u.output_tokens} tokens, ${u.cost_usd:.4f}")
    if v.dropped:
        status.append(f"{len(v.dropped)} unsupported item(s) removed")
    if v.retries:
        status.append("retried once")
    if v.fallback_used:
        status.append("summary generated from the report data (model text did not pass checks)")
    if v.error:
        status.append(f"model error: {v.error}")
    lines += ["", exp.caveat, exp.disclaimer]
    if status:
        lines += ["", "(" + "; ".join(status) + ")"]
    return "\n".join(lines)
