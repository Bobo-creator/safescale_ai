"""`safescale` command-line entry point."""

import argparse
import logging
from pathlib import Path

from safescale import config, db
from safescale.ingest import run_ingest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="safescale", description="SafeScale AI data pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="apply pending SQL migrations from db/migrations")

    ingest = commands.add_parser("ingest", help="fetch CPSC recalls and load them into Postgres")
    ingest.add_argument(
        "--snapshot", type=Path, help="load from a saved snapshot instead of calling the API"
    )
    ingest.add_argument("--limit", type=int, help="load only the first N records (thin slice)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
