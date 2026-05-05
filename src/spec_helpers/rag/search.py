"""
search.py — semantic search over the RAG index

Canonical source for this module. The standalone script at rag/search.py
contains the same logic for users who prefer the curl-install path.

Loads pre-built embeddings, embeds the query with the model recorded in
manifest.json, and returns top-k chunks ranked by cosine similarity.
All progress messages go to stderr; stdout is always clean JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from spec_helpers.rag import rag_index_dir, ensure_model


def load_index(specs_dir: Path) -> tuple[list[dict], np.ndarray]:
    rag_dir = rag_index_dir(specs_dir)
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
    return chunks, np.load(str(embeddings_path))


def load_model(specs_dir: Path) -> SentenceTransformer:
    manifest_path = rag_index_dir(specs_dir) / "manifest.json"
    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    if manifest_path.exists():
        model_id = json.loads(manifest_path.read_text()).get("model", model_id)
    resolved = ensure_model(model_id)
    return SentenceTransformer(resolved)


def search(specs_dir: Path, query: str, k: int = 5) -> list[dict]:
    """Return the *k* chunks most semantically similar to *query*."""
    chunks, vectors = load_index(specs_dir)
    model = load_model(specs_dir)
    q = model.encode(query, normalize_embeddings=True)
    scores = vectors @ q
    top = np.argsort(scores)[::-1][:k]
    return [
        {
            "score": round(float(scores[i]), 4),
            "spec_id": chunks[i]["spec_id"],
            "path": chunks[i]["path"],
            "start": chunks[i]["start"],
            "text": chunks[i]["text"],
        }
        for i in top
    ]


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "usage: python -m spec_helpers.rag.search <specs-dir> <query> [<top-k>]",
            file=sys.stderr,
        )
        sys.exit(1)
    specs_dir = Path(sys.argv[1])
    query = sys.argv[2]
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    print(json.dumps(search(specs_dir, query, k), indent=2))


if __name__ == "__main__":
    main()
