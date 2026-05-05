#!/usr/bin/env python3
"""
search.py — standalone script for the curl-install path

Canonical source: src/spec_helpers/rag/search.py (used by the pipx package).
Keep these two files in sync when changing search logic.

Usage:
  python rag/search.py <specs-dir> "<query>" [<top-k>]

For the pipx-based install use: spec-index rag-search
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


# ── core functions ─────────────────────────────────────────────────────────────


def load_index(specs_dir: Path) -> tuple[list[dict], np.ndarray]:
    """Load chunks and embedding matrix from *specs_dir*/rag/."""
    rag_dir = specs_dir / "rag"
    chunks_path = rag_dir / "chunks.jsonl"
    embeddings_path = rag_dir / "embeddings.npy"

    if not chunks_path.exists() or not embeddings_path.exists():
        print(
            f"error: RAG index not found at {rag_dir}\n"
            "       run: spec-index rag-build",
            file=sys.stderr,
        )
        sys.exit(1)

    chunks = [
        json.loads(line)
        for line in chunks_path.read_text().splitlines()
        if line.strip()
    ]
    vectors = np.load(str(embeddings_path))
    return chunks, vectors


def load_model(specs_dir: Path) -> SentenceTransformer:
    """Read the model ID from the manifest and load it."""
    manifest_path = specs_dir / "rag" / "manifest.json"
    if manifest_path.exists():
        model_id = json.loads(manifest_path.read_text()).get(
            "model", "sentence-transformers/all-MiniLM-L6-v2"
        )
    else:
        model_id = "sentence-transformers/all-MiniLM-L6-v2"

    print(f"loading model {model_id}…", file=sys.stderr)
    return SentenceTransformer(model_id)


def search(specs_dir: Path, query: str, k: int = 5) -> list[dict]:
    """Return the *k* chunks most semantically similar to *query*."""
    chunks, vectors = load_index(specs_dir)
    model = load_model(specs_dir)

    q = model.encode(query, normalize_embeddings=True)
    scores = vectors @ q
    top_indices = np.argsort(scores)[::-1][:k]

    return [
        {
            "score": round(float(scores[i]), 4),
            "spec_id": chunks[i]["spec_id"],
            "path": chunks[i]["path"],
            "start": chunks[i]["start"],
            "text": chunks[i]["text"],
        }
        for i in top_indices
    ]


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python rag/search.py <specs-dir> <query> [<top-k>]", file=sys.stderr)
        sys.exit(1)

    specs_dir = Path(sys.argv[1])
    query = sys.argv[2]
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    results = search(specs_dir, query, k)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
