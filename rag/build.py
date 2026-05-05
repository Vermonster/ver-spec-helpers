#!/usr/bin/env python3
"""
build.py — standalone script for the curl-install path

Canonical source: src/spec_helpers/rag/build.py (used by the pipx package).
Keep these two files in sync when changing chunk/embed logic.

Usage:
  python rag/build.py <specs-dir>

For the pipx-based install use: spec-index rag-build
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# ── configuration ─────────────────────────────────────────────────────────────

MODEL_ID: str = os.environ.get(
    "SPEC_RAG_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
CHUNK_SIZE: int = int(os.environ.get("SPEC_CHUNK_SIZE", "900"))
CHUNK_OVERLAP: int = int(os.environ.get("SPEC_CHUNK_OVERLAP", "150"))


# ── core functions ─────────────────────────────────────────────────────────────


def chunk_text(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[int, str]]:
    """Split *text* into overlapping windows.

    Returns a list of (start_offset, chunk_text) pairs.
    """
    chunks: list[tuple[int, str]] = []
    i = 0
    while i < len(text):
        chunks.append((i, text[i : i + size]))
        i += size - overlap
    return chunks


def iter_specs(specs_dir: Path):
    """Yield ``(spec_id, path, text)`` for every ``spec.md`` under *specs_dir*."""
    for path in sorted(specs_dir.rglob("spec.md")):
        yield path.parent.name, path, path.read_text(errors="ignore")


def build_index(specs_dir: Path, model: SentenceTransformer) -> None:
    """Embed all spec chunks and write the RAG index to *specs_dir*/rag/."""
    rag_dir = specs_dir / "rag"
    rag_dir.mkdir(exist_ok=True)

    rows: list[dict] = []
    vectors: list[np.ndarray] = []
    spec_count = 0

    for spec_id, spec_path, text in iter_specs(specs_dir):
        spec_count += 1
        # Store paths relative to specs_dir's parent so they work from repo root
        rel_path = str(spec_path.relative_to(specs_dir.parent))

        for n, (start, chunk) in enumerate(chunk_text(text)):
            rows.append(
                {
                    "id": f"{spec_id}#{n:04d}",
                    "spec_id": spec_id,
                    "path": rel_path,
                    "start": start,
                    "text": chunk,
                }
            )
            vectors.append(model.encode(chunk, normalize_embeddings=True))

    if not rows:
        print(f"error: no spec.md files found in {specs_dir}", file=sys.stderr)
        sys.exit(1)

    # chunks.jsonl — one record per line
    chunks_path = rag_dir / "chunks.jsonl"
    with chunks_path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    # embeddings.npy — float32 matrix, rows match chunks.jsonl
    matrix = np.vstack(vectors).astype("float32")
    np.save(str(rag_dir / "embeddings.npy"), matrix)

    # manifest.json — build metadata for freshness checks
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
    if len(sys.argv) < 2:
        print("usage: python rag/build.py <specs-dir>", file=sys.stderr)
        sys.exit(1)

    specs_dir = Path(sys.argv[1])
    if not specs_dir.is_dir():
        print(f"error: not a directory: {specs_dir}", file=sys.stderr)
        sys.exit(1)

    print("loading embedding model…", file=sys.stderr)
    model = SentenceTransformer(MODEL_ID)
    build_index(specs_dir, model)


if __name__ == "__main__":
    main()
