#!/usr/bin/env python3
"""
build.py — standalone script for the curl-install path

Canonical source: src/spec_helpers/rag/build.py (used by the pipx package).
Keep these two files in sync when changing chunk/embed logic.

Usage:
  python rag/build.py <specs-dir>
  python rag/build.py --print-dir <specs-dir>   # print index path and exit

For the pipx-based install use: spec-index rag-build
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_ID: str = os.environ.get(
    "SPEC_RAG_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
CHUNK_SIZE: int = int(os.environ.get("SPEC_CHUNK_SIZE", "900"))
CHUNK_OVERLAP: int = int(os.environ.get("SPEC_CHUNK_OVERLAP", "150"))


# ── path helpers (inlined; canonical copy in src/spec_helpers/rag/__init__.py) ─


def ver_spec_home() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        root = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = Path.cwd()
    home = root / ".ver-spec-helpers"
    home.mkdir(exist_ok=True)
    return home


def rag_index_dir(specs_dir: Path) -> Path:  # noqa: ARG001
    override = os.environ.get("SPEC_RAG_INDEX_DIR")
    if override:
        return Path(override)
    return ver_spec_home() / "rag"


def resolve_model(model_id: str) -> str:
    model_name = model_id.split("/")[-1]
    candidates: list[Path] = []
    if "SPEC_RAG_MODELS_DIR" in os.environ:
        candidates.append(Path(os.environ["SPEC_RAG_MODELS_DIR"]) / model_name)
    candidates.append(ver_spec_home() / "models" / model_name)
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.iterdir()):
            return str(candidate)
    return model_id


# ── core functions ─────────────────────────────────────────────────────────────


def chunk_text(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    i = 0
    while i < len(text):
        chunks.append((i, text[i : i + size]))
        i += size - overlap
    return chunks


def iter_specs(specs_dir: Path):
    for path in sorted(specs_dir.rglob("spec.md")):
        yield path.parent.name, path, path.read_text(errors="ignore")


def build_index(specs_dir: Path, model: SentenceTransformer) -> None:
    rag_dir = rag_index_dir(specs_dir)
    rag_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    vectors: list[np.ndarray] = []
    spec_count = 0

    for spec_id, spec_path, text in iter_specs(specs_dir):
        spec_count += 1
        rel_path = str(spec_path.relative_to(specs_dir.parent))
        for n, (start, chunk) in enumerate(chunk_text(text)):
            rows.append({
                "id": f"{spec_id}#{n:04d}",
                "spec_id": spec_id,
                "path": rel_path,
                "start": start,
                "text": chunk,
            })
            vectors.append(model.encode(chunk, normalize_embeddings=True))

    if not rows:
        print(f"error: no spec.md files found in {specs_dir}", file=sys.stderr)
        sys.exit(1)

    with (rag_dir / "chunks.jsonl").open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    np.save(str(rag_dir / "embeddings.npy"), np.vstack(vectors).astype("float32"))

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "specs_dir": str(specs_dir),
        "model": MODEL_ID,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "spec_count": spec_count,
        "chunk_count": len(rows),
    }
    (rag_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built {rag_dir} ({spec_count} specs, {len(rows)} chunks)")


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    args = sys.argv[1:]

    if "--print-dir" in args:
        args = [a for a in args if a != "--print-dir"]
        specs_dir = Path(args[0]) if args else Path(".")
        print(rag_index_dir(specs_dir))
        return

    if not args:
        print("usage: python rag/build.py <specs-dir>", file=sys.stderr)
        sys.exit(1)

    specs_dir = Path(args[0])
    if not specs_dir.is_dir():
        print(f"error: not a directory: {specs_dir}", file=sys.stderr)
        sys.exit(1)

    print("loading embedding model…", file=sys.stderr)
    build_index(specs_dir, SentenceTransformer(resolve_model(MODEL_ID)))


if __name__ == "__main__":
    main()
