"""Explain benchmark: 10 product descriptions x 2 models on the production data (Supabase).

Run from pipeline/:  uv run python ../evaluation/explain_benchmark/run.py
Writes results.json (one row per query x model) and ../explain_review/review.md (the owner's
human-review sheet, from the default model's explanations). Costs about $0.25 in total.
"""

import json
import os
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

from safescale import config, db
from safescale.analysis.analyze import analyze
from safescale.explain.explain import explain
from safescale.explain.explainer import DEFAULT_EFFORT, DEFAULT_MODEL, OpenAIExplainer
from safescale.retrieval.embedder import OpenAIEmbedder

HERE = Path(__file__).parent
QUERIES = [
    "Rechargeable children's night light using a 2000 mAh lithium-ion battery, USB-C charging, "
    "ABS plastic housing, and LED lighting.",
    "Wooden baby crib with adjustable mattress height and a drop-down side rail.",
    "Six-drawer wooden dresser for a child's bedroom, 48 inches tall.",
    "Folding electric bicycle with a 48 V lithium battery pack and hydraulic disc brakes.",
    "Electric space heater, 1500 W ceramic element, tip-over switch, for bedrooms.",
    "Children's hooded sweatshirt with a drawstring, cotton, sizes 2T to 5T.",
    "Magnetic building tiles toy set for ages 3 and up, with small neodymium magnets.",
    "Portable butane camping stove with a piezo igniter.",
    "Self-balancing hoverboard scooter with a lithium-ion battery and LED lights.",
    "Glass French press coffee maker, 1 liter, with a stainless steel plunger.",
]
# BENCH_MODELS=gpt-6-luna,gpt-6.1-sol (default: both); reasoning effort from EXPLAIN_REASONING_EFFORT.
MODELS = os.environ.get("BENCH_MODELS", f"{DEFAULT_MODEL},gpt-6.1-sol").split(",")
REVIEW_COUNT = 5


def main() -> None:
    config.load_dotenv()
    embedder = OpenAIEmbedder()
    rows, reviews = [], []
    with db.connect() as conn:
        for qi, query in enumerate(QUERIES, 1):
            report = analyze(conn, query, embedder=embedder, k=25)
            for model in MODELS:
                started = time.perf_counter()
                exp = explain(conn, report, explainer=OpenAIExplainer(model=model))
                seconds = time.perf_counter() - started
                v = exp.validation
                items = (
                    len(exp.summary)
                    + sum(len(h.sentences) for h in exp.hazards)
                    + len(exp.match_reasons)
                    + len(exp.investigation_notes)
                )
                rows.append(
                    {
                        "query_id": qi,
                        "query": query,
                        "model": model,
                        "signal": report.overall_signal,
                        "relevant": report.relevant,
                        "insufficient_evidence": report.insufficient_evidence,
                        "generated": exp.generated,
                        "first_try_clean": v.first_try_clean,
                        "retries": v.retries,
                        "fallback_used": v.fallback_used,
                        "dropped": [asdict(d) for d in v.dropped],
                        "items_shown": items,
                        "error": v.error,
                        "seconds": round(seconds, 2),
                        **asdict(exp.usage),
                    }
                )
                print(
                    f"q{qi:<2} {model:<12} {report.overall_signal:<8} clean={v.first_try_clean!s:<5} "
                    f"dropped={len(v.dropped)} retries={v.retries} fallback={v.fallback_used!s:<5} "
                    f"{seconds:5.1f}s ${exp.usage.cost_usd:.4f}",
                    flush=True,
                )
                if model == DEFAULT_MODEL and exp.generated and len(reviews) < REVIEW_COUNT:
                    ids = [m.recall_id for m in report.matches]
                    descriptions = dict(
                        conn.execute(
                            "select recall_id, description from recalls where recall_id = any(%s)",
                            (ids,),
                        ).fetchall()
                    )
                    reviews.append((qi, query, report, exp, descriptions))
    (HERE / "results.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    summarize(rows)
    write_review_sheet(reviews)


def summarize(rows: list[dict]) -> None:
    for model in MODELS:
        r = [x for x in rows if x["model"] == model and not x["insufficient_evidence"]]
        secs = [x["seconds"] for x in r]
        print(
            f"\n{model}: {len(r)} explanations | first-try clean {sum(x['first_try_clean'] for x in r)}"
            f"/{len(r)} | items dropped {sum(len(x['dropped']) for x in r)} | retries "
            f"{sum(x['retries'] for x in r)} | fallback {sum(x['fallback_used'] for x in r)} | "
            f"median {statistics.median(secs):.1f}s (max {max(secs):.1f}s) | "
            f"mean ${statistics.mean(x['cost_usd'] for x in r):.4f}"
        )


def write_review_sheet(reviews) -> None:
    out = HERE.parent / "explain_review" / "review.md"
    out.parent.mkdir(exist_ok=True)
    lines = [
        "# Explanation review sheet",
        "",
        f"{len(reviews)} explanations by `{DEFAULT_MODEL}` (reasoning effort "
        f"`{os.environ.get('EXPLAIN_REASONING_EFFORT', DEFAULT_EFFORT)}`). For every numbered sentence, read the "
        "cited recalls underneath and tick **supported** only if they back the claim. Otherwise "
        "tick **not supported** and add a word on why. Judge only support by the cited recalls, "
        "not style.",
        "",
    ]
    n = 0
    for qi, query, report, exp, descriptions in reviews:
        recalls = {m.recall_id: m for m in report.matches}
        lines += [f"## Q{qi}. {query}", "", f"Signal: **{report.overall_signal}**", ""]
        claims = [("Summary", s) for s in exp.summary]
        claims += [(f"Hazard: {h.category}", s) for h in exp.hazards for s in h.sentences]
        claims += [(f"Investigation: {i.area_id}", i.sentence) for i in exp.investigation_notes]
        for section, sentence in claims:
            n += 1
            lines += [
                f"**{n}. ({section})** {sentence.text}",
                "",
                "- [ ] supported   - [ ] not supported — why: ",
                "",
            ]
            for rid in sentence.citations:
                m = recalls[rid]
                lines.append(f"  > **#{rid}** {m.title} — {m.hazard_text or '(no hazard text)'}")
            lines.append("")
        for reason in exp.match_reasons:
            n += 1
            m = recalls[reason.recall_id]
            lines += [
                f"**{n}. (Why it matches #{reason.recall_id})** shared: {', '.join(reason.shared)}"
                + (f" · different: {', '.join(reason.different)}" if reason.different else ""),
                "",
                "- [ ] supported   - [ ] not supported — why: ",
                "",
                f"  > **#{reason.recall_id}** {m.title} — {m.hazard_text or '(no hazard text)'}",
                f"  > *Description:* {(descriptions.get(reason.recall_id) or '(none)')[:600]}",
                "",
            ]
    lines.insert(4, f"Total: **{n} items**.\n")
    out.write_text("\n".join(lines) + "\n")
    print(f"\nreview sheet: {out} ({n} items)")


if __name__ == "__main__":
    sys.exit(main())
