"""`safescale` command-line entry point."""

import argparse
import logging
from pathlib import Path

from safescale import config, db
from safescale.ingest import run_ingest
from safescale.retrieval.embedder import Embedder, OpenAIEmbedder
from safescale.retrieval.index import embed_recalls
from safescale.retrieval.search import METHODS, Hit, search


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
    return parser


def make_embedder() -> Embedder:
    return OpenAIEmbedder()


def format_hits(hits: list[Hit]) -> str:
    if not hits:
        return "no matching recalls"
    lines = []
    for hit in hits:
        lines.append(f"{hit.rank:>3}. [{hit.score:.3f}] {hit.recall_date}  {hit.title}")
        lines.append(f"     {hit.url}")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
