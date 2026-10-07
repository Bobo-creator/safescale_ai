from safescale.cli import build_parser


def test_cli_exposes_migrate_and_ingest():
    parser = build_parser()
    assert parser.parse_args(["migrate"]).command == "migrate"
    args = parser.parse_args(["ingest", "--limit", "5"])
    assert (args.command, args.limit, args.snapshot) == ("ingest", 5, None)
