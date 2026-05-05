"""
cli.py — spec-index command-line interface

Entry point registered in pyproject.toml:
  spec-index = "spec_helpers.cli:main"

Provides all seven commands:
  build, check, list, stats          YAML index (no model required)
  rag-build, rag-search, rag-check   semantic RAG index
"""

from __future__ import annotations

import argparse
import json
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-index",
        description="Manage the spec library context index.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── YAML commands ──────────────────────────────────────────────────────────
    for name, help_text in [
        ("build", "Parse all spec files and write index.yaml"),
        ("check", "Exit 1 if index is missing or stale (use in CI / pre-commit)"),
        ("list",  "Print id, domain, and summary for each spec"),
        ("stats", "Show token budget and domain breakdown"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>",
                       help="auto-detected if omitted")

    # ── RAG commands ───────────────────────────────────────────────────────────
    rb = sub.add_parser("rag-build", help="Chunk + embed specs; write RAG index")
    rb.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>")

    rs = sub.add_parser("rag-search",
                        help="Semantic search; prints JSON array to stdout")
    rs.add_argument("query", metavar="<query>")
    rs.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>")
    rs.add_argument("-k", "--top-k", type=int, default=5,
                    dest="top_k", metavar="K",
                    help="number of results (default: 5)")

    rc = sub.add_parser("rag-check",
                        help="Exit 1 if RAG index is missing or stale")
    rc.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>")

    rd = sub.add_parser("rag-dir",
                        help="Print the RAG index directory for this project")
    rd.add_argument("specs_dir", nargs="?", default=None, metavar="<specs-dir>")

    return parser


def main() -> None:  # noqa: C901
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    from spec_helpers.indexer import require_specs_dir

    # ── YAML commands ──────────────────────────────────────────────────────────

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

    # ── RAG commands ───────────────────────────────────────────────────────────

    elif args.command == "rag-build":
        from sentence_transformers import SentenceTransformer
        from spec_helpers.rag import resolve_model
        from spec_helpers.rag.build import MODEL_ID, build_index
        specs_dir = require_specs_dir(args.specs_dir)
        resolved = resolve_model(MODEL_ID)
        if resolved == MODEL_ID:
            print(
                f"loading {MODEL_ID} via HF Hub\n"
                "  tip: run 'make download-model' to save it to .ver-spec-helpers/models/ "
                "and avoid this network call",
                file=sys.stderr,
            )
        else:
            print(f"loading model from {resolved}", file=sys.stderr)
        build_index(specs_dir, SentenceTransformer(resolved))

    elif args.command == "rag-search":
        from spec_helpers.rag.search import search
        specs_dir = require_specs_dir(args.specs_dir)
        results = search(specs_dir, args.query, args.top_k)
        print(json.dumps(results, indent=2))

    elif args.command == "rag-check":
        from spec_helpers.rag import rag_index_dir
        specs_dir = require_specs_dir(args.specs_dir)
        manifest = rag_index_dir(specs_dir) / "manifest.json"

        if not manifest.exists():
            print(
                f"stale: RAG index does not exist "
                f"(run: spec-index rag-build {specs_dir})",
                file=sys.stderr,
            )
            sys.exit(1)

        spec_files = sorted(specs_dir.rglob("spec.md"))
        mtime = manifest.stat().st_mtime
        newer = [f for f in spec_files if f.stat().st_mtime > mtime]
        if newer:
            print(
                f"stale: {len(newer)} spec file(s) modified after RAG index was built "
                f"(run: spec-index rag-build {specs_dir})",
                file=sys.stderr,
            )
            sys.exit(1)

        data = json.loads(manifest.read_text())
        indexed = data.get("spec_count", 0)
        if len(spec_files) != indexed:
            print(
                f"stale: {len(spec_files)} spec files but manifest records {indexed} "
                f"(run: spec-index rag-build {specs_dir})",
                file=sys.stderr,
            )
            sys.exit(1)

        chunk_count = data.get("chunk_count", 0)
        print(f"ok: RAG index is current ({indexed} specs, {chunk_count} chunks)")

    elif args.command == "rag-dir":
        from spec_helpers.rag import rag_index_dir
        specs_dir = require_specs_dir(args.specs_dir)
        print(rag_index_dir(specs_dir))
