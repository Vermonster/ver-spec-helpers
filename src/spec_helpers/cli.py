"""
cli.py — spec-index command-line interface

Entry point registered in pyproject.toml:
  spec-index = "spec_helpers.cli:main"

Provides six commands: build, check, list, stats, eval, coverage
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-index",
        description="Manage the spec library context index.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    for name, help_text in [
        ("build",    "Parse all spec files and write index.yaml"),
        ("check",    "Exit 1 if index is missing or stale (use in CI / pre-commit)"),
        ("list",     "Print id, domain, and summary for each spec"),
        ("stats",    "Show token budget and domain breakdown"),
        ("coverage", "Show signal richness (symbols, headings, paths) per spec"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>",
                       help="auto-detected if omitted")

    ev = sub.add_parser("eval", help="Score specs against a query; simulate selection")
    ev.add_argument("query", metavar="<query>")
    ev.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>")
    ev.add_argument("--budget", type=int, default=4000, metavar="TOKENS",
                    help="token budget for selection (default: 4000)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    from spec_helpers.indexer import require_specs_dir

    if args.command == "build":
        from spec_helpers.indexer import cmd_build
        cmd_build(require_specs_dir(args.specs_dir))

    elif args.command == "check":
        from spec_helpers.indexer import cmd_check
        cmd_check(require_specs_dir(args.specs_dir))

    elif args.command == "list":
        from spec_helpers.indexer import cmd_list
        cmd_list(require_specs_dir(args.specs_dir))

    elif args.command == "stats":
        from spec_helpers.indexer import cmd_stats
        cmd_stats(require_specs_dir(args.specs_dir))

    elif args.command == "coverage":
        from spec_helpers.indexer import cmd_coverage
        cmd_coverage(require_specs_dir(args.specs_dir))

    elif args.command == "eval":
        from spec_helpers.indexer import cmd_eval
        cmd_eval(require_specs_dir(args.specs_dir), args.query, args.budget)
