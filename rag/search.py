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
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


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


def ensure_model(model_id: str) -> str:
    resolved = resolve_model(model_id)
    if resolved != model_id:
        print(f"loading model from {resolved}", file=sys.stderr)
        return resolved
    from sentence_transformers import SentenceTransformer  # lazy import
    model_name = model_id.split("/")[-1]
    local_path = ver_spec_home() / "models" / model_name
    print(f"downloading {model_id} to {local_path} (one-time setup)\u2026", file=sys.stderr)
    SentenceTransformer(model_id).save(str(local_path))
    print(f"\u2713  model saved to {local_path}", file=sys.stderr)
    return str(local_path)


# ── core functions ─────────────────────────────────────────────────────────────


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


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python rag/search.py <specs-dir> <query> [<top-k>]", file=sys.stderr)
        sys.exit(1)

    specs_dir = Path(sys.argv[1])
    query = sys.argv[2]
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    print(json.dumps(search(specs_dir, query, k), indent=2))


if __name__ == "__main__":
    main()
