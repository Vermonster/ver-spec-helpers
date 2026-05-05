"""
build.py — chunk and embed spec files for local RAG search

Canonical source for this module. The standalone script at rag/build.py
contains the same logic for users who prefer the curl-install path.

Produces three files in .ver-spec-helpers/rag/:
  chunks.jsonl    one JSON object per chunk, rows match embeddings.npy
  embeddings.npy  float32 matrix, L2-normalised (dot-product = cosine sim)
  manifest.json   build metadata used by rag-check for staleness detection

Environment overrides:
  SPEC_RAG_MODEL    embedding model id  (default: all-MiniLM-L6-v2)
  SPEC_CHUNK_SIZE   characters per chunk (default: 900)
  SPEC_CHUNK_OVERLAP overlap between chunks (default: 150)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from spec_helpers.rag import rag_index_dir, resolve_model

MODEL_ID: str = os.environ.get(
    "SPEC_RAG_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
CHUNK_SIZE: int = int(os.environ.get("SPEC_CHUNK_SIZE", "900"))
CHUNK_OVERLAP: int = int(os.environ.get("SPEC_CHUNK_OVERLAP", "150"))


    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[int, str]]:
    """Split *text* into overlapping windows of *size* chars."""
    chunks: list[tuple[int, str]] = []
    i = 0
    while i < len(text):
        chunks.append((i, text[i : i + size]))
        i += size - overlap
    return chunks


def iter_specs(specs_dir: Path):
    """Yield ``(spec_id, path, text)`` for every spec.md under *specs_dir*."""
    for path in sorted(specs_dir.rglob("spec.md")):
        yield path.parent.name, path, path.read_text(errors="ignore")


def build_index(specs_dir: Path, model: SentenceTransformer) -> None:
    """Embed all spec chunks and write the RAG index to .ver-spec-helpers/rag/."""
    rag_dir = rag_index_dir(specs_dir)
    rag_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    vectors: list[np.ndarray] = []
    spec_count = 0

    for spec_id, spec_path, text in iter_specs(specs_dir):
        spec_count += 1
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

    chunks_path = rag_dir / "chunks.jsonl"
    with chunks_path.open("w") as fh:
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


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m spec_helpers.rag.build <specs-dir>", file=sys.stderr)
        sys.exit(1)
    specs_dir = Path(sys.argv[1])
    if not specs_dir.is_dir():
        print(f"error: not a directory: {specs_dir}", file=sys.stderr)
        sys.exit(1)
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


if __name__ == "__main__":
    main()
