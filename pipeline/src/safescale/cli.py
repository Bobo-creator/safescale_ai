"""`safescale` command-line entry point."""

import argparse
import logging
from pathlib import Path

from safescale import config


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
        raise NotImplementedError("migrate is implemented in task 2")
    if args.command == "ingest":
        raise NotImplementedError("ingest is implemented in task 7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
