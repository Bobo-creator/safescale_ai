"""`safescale` command-line entry point."""

import argparse
import json
import logging
import time
from pathlib import Path

from safescale import config, db
from safescale.analysis.analyze import analyze
from safescale.analysis.terms import refresh_term_stats
from safescale.analysis.text import format_report
from safescale.explain.explain import explain
from safescale.explain.explainer import Explainer, OpenAIExplainer
from safescale.explain.text import format_explanation
from safescale.ingest import run_ingest
from safescale.retrieval.embedder import Embedder, OpenAIEmbedder
from safescale.retrieval.index import embed_recalls
from safescale.retrieval.search import METHODS, Hit, search
from safescale.taxonomy.classify import Classification
from safescale.taxonomy.labeling import gold as gold_file
from safescale.taxonomy.score import format_score, score
from safescale.taxonomy.store import classify_all, labels_for

DEFAULT_GOLD_PATH = config.REPO_ROOT / "evaluation" / "hazard_gold" / "gold.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="safescale", description="SafeScale AI data pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="apply pending SQL migrations from db/migrations")

    ingest = commands.add_parser("ingest", help="fetch CPSC recalls and load them into Postgres")
    ingest.add_argument(
        "--snapshot", type=Path, help="load from a saved snapshot instead of calling the API"
    )
    ingest.add_argument("--limit", type=int, help="load only the first N records (thin slice)")

    embed = commands.add_parser("embed", help="embed recalls that are new or changed")
    embed.add_argument("--limit", type=int, help="embed at most N recalls (trial run)")

    find = commands.add_parser("search", help="find recalls similar to a product description")
    find.add_argument("query", help="product description, in quotes")
    find.add_argument("--k", type=int, default=10, help="number of results (default 10)")
    find.add_argument("--method", choices=METHODS, default="vector")

    report = commands.add_parser("analyze", help="hazard report for a product description")
    report.add_argument("query", help="product description, in quotes")
    report.add_argument("--k", type=int, default=25, help="similar recalls to analyze (default 25)")
    report.add_argument("--method", choices=METHODS, default="vector")
    report.add_argument("--json", action="store_true", help="print the report as JSON")

    why = commands.add_parser(
        "explain", help="hazard report plus a cited, plain-language explanation"
    )
    why.add_argument("query", help="product description, in quotes")
    why.add_argument("--k", type=int, default=25, help="similar recalls to analyze (default 25)")
    why.add_argument("--method", choices=METHODS, default="vector")
    why.add_argument("--model", help="explanation model (default: EXPLAIN_MODEL or gpt-6-luna)")
    why.add_argument("--json", action="store_true", help="print report and explanation as JSON")

    commands.add_parser("classify", help="(re)label every recall with hazard categories")
    hazards = commands.add_parser("hazards", help="show a recall's hazard labels and evidence")
    hazards.add_argument("recall_id", type=int)

    scorer = commands.add_parser("score-hazards", help="score the classifier against gold labels")
    scorer.add_argument("--gold", type=Path, default=DEFAULT_GOLD_PATH, help="gold file path")

    label = commands.add_parser("label", help="open the local page for labeling the gold sample")
    label.add_argument("--gold", type=Path, default=DEFAULT_GOLD_PATH, help="gold file path")
    label.add_argument("--n", type=int, default=gold_file.DEFAULT_SAMPLE_SIZE, help="sample size")
    label.add_argument("--seed", type=int, default=gold_file.DEFAULT_SEED, help="sample seed")
    label.add_argument("--port", type=int, default=8765)
    label.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    return parser


def make_embedder() -> Embedder:
    return OpenAIEmbedder()


def make_explainer(model: str | None = None) -> Explainer:
    return OpenAIExplainer(model=model)


def format_hits(hits: list[Hit]) -> str:
    if not hits:
        return "no matching recalls"
    lines = []
    for hit in hits:
        lines.append(f"{hit.rank:>3}. [{hit.score:.3f}] {hit.recall_date}  {hit.title}")
        lines.append(f"     {hit.url}")
    return "\n".join(lines)


def format_classification(result: Classification) -> str:
    lines = [f'{lbl.category:<26} <- "{lbl.evidence}" ({lbl.source})' for lbl in result.labels]
    for v in result.violations:
        lines.append(
            f'violates {v.standard or "a standard (unnamed)"} <- "{v.evidence}" ({v.source})'
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per HTTP request is noise
    config.load_dotenv()

    if args.command == "migrate":
        with db.connect() as conn:
            applied = db.migrate(conn)
        print(f"applied {len(applied)} migration(s): {', '.join(applied) or 'up to date'}")
    if args.command == "ingest":
        with db.connect() as conn:
            summary = run_ingest(conn, snapshot=args.snapshot, limit=args.limit)
        r = summary.result
        print(
            f"run {summary.run_id}: fetched={summary.fetched} inserted={r.inserted} "
            f"updated={r.updated} unchanged={r.unchanged} rejected={summary.rejected} "
            f"snapshot={summary.snapshot}"
        )
    if args.command == "embed":
        embedder = make_embedder()
        with db.connect() as conn:
            result = embed_recalls(conn, embedder, limit=args.limit)
        print(f"embedded {result.embedded} recall(s) with {embedder.model}; {result.tokens} tokens")
    if args.command == "search":
        embedder = make_embedder() if args.method != "keyword" else None
        with db.connect() as conn:
            hits = search(conn, args.query, k=args.k, method=args.method, embedder=embedder)
        print(format_hits(hits))
    if args.command == "analyze":
        with db.connect() as conn:
            result = analyze(
                conn, args.query, embedder=make_embedder(), k=args.k, method=args.method
            )
        print(json.dumps(result.to_dict(), indent=2) if args.json else format_report(result))
    if args.command == "explain":
        with db.connect() as conn:
            report = analyze(
                conn, args.query, embedder=make_embedder(), k=args.k, method=args.method
            )
            explanation = explain(conn, report, explainer=make_explainer(args.model))
        if args.json:
            body = {"report": report.to_dict(), "explanation": explanation.to_dict()}
            print(json.dumps(body, indent=2))
        else:
            print(format_explanation(report, explanation))
    if args.command == "classify":
        started = time.perf_counter()
        with db.connect() as conn:
            result = classify_all(conn)
            refresh_term_stats(conn)  # term frequencies used by `analyze`
        elapsed = time.perf_counter() - started
        print(
            f"classified {result.recalls} recalls in {elapsed:.1f}s: {result.labels} labels, "
            f"{result.other_only} 'other' only, {result.flagged} with a standards violation"
        )
        for category, count in result.by_category.items():
            print(f"  {category:<26} {count:>6}")
    if args.command == "hazards":
        with db.connect() as conn:
            found = labels_for(conn, [args.recall_id])
        if args.recall_id not in found:
            print(f"recall {args.recall_id} not found or not classified (run `safescale classify`)")
            return 1
        print(format_classification(found[args.recall_id]))
    if args.command == "score-hazards":
        if not args.gold.exists():
            print(f"no gold file at {args.gold}; run `safescale label` first")
            return 1
        print(format_score(score(gold_file.load_gold(args.gold))))
    if args.command == "label":
        run_labeling(args)
    return 0


def run_labeling(args: argparse.Namespace) -> None:
    import webbrowser

    from safescale.taxonomy.labeling.server import LabelingServer

    if args.gold.exists():
        gold = gold_file.load_gold(args.gold)
        if (len(gold.items), gold.seed) != (args.n, args.seed):
            print(
                f"note: resuming {args.gold} ({len(gold.items)} recalls, seed {gold.seed}); "
                "--n/--seed only apply to a new gold file"
            )
    else:
        with db.connect() as conn:
            gold = gold_file.create_gold_set(conn, n=args.n, seed=args.seed)
        gold_file.save_gold(gold, args.gold)
        print(f"created {args.gold} with {len(gold.items)} recalls (seed {gold.seed})")

    done = sum(item.is_labeled for item in gold.items)
    server = LabelingServer(gold, args.gold, port=args.port)
    print(
        f"{done}/{len(gold.items)} labeled. Labeling page: {server.url}  (Ctrl+C to stop)",
        flush=True,
    )
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped; labels are saved")
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
