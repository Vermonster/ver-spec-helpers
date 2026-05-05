"""Shared path utilities for the RAG subpackage.

All functions that compute filesystem paths live here so build.py and
search.py stay in sync without duplicating logic. The standalone scripts
at rag/build.py and rag/search.py inline equivalent implementations.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def ver_spec_home() -> Path:
    """Return ``<project-root>/.ver-spec-helpers``, creating it if necessary.

    Uses git to find the project root; falls back to cwd if not in a repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        root = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = Path.cwd()

    home = root / ".ver-spec-helpers"
    home.mkdir(exist_ok=True)
    return home


def rag_index_dir(specs_dir: Path) -> Path:  # noqa: ARG001
    """Return ``.ver-spec-helpers/rag/``.

    Override with ``SPEC_RAG_INDEX_DIR`` (absolute path) when you need the
    index stored elsewhere.
    """
    override = os.environ.get("SPEC_RAG_INDEX_DIR")
    if override:
        return Path(override)
    return ver_spec_home() / "rag"


def resolve_model(model_id: str) -> str:
    """Return a local model path if one exists, otherwise the HF Hub model ID.

    Search order:
    1. ``SPEC_RAG_MODELS_DIR/<model-name>``          (explicit env override)
    2. ``.ver-spec-helpers/models/<model-name>``     (project default)
    3. *model_id* as-is                              (HF Hub download)

    Run ``make download-model`` to populate ``.ver-spec-helpers/models/``.
    """
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
    """Return a local model path, downloading to .ver-spec-helpers/models/ if needed.

    Called by ``rag-build`` so the model is always stored locally after the
    first index build. Subsequent ``rag-build`` and ``rag-search`` calls find
    the local copy via :func:`resolve_model` and make no network requests.
    """
    resolved = resolve_model(model_id)
    if resolved != model_id:
        print(f"loading model from {resolved}", file=sys.stderr)
        return resolved

    # Not cached locally — download and save
    from sentence_transformers import SentenceTransformer  # lazy import

    model_name = model_id.split("/")[-1]
    local_path = ver_spec_home() / "models" / model_name
    print(
        f"downloading {model_id} to {local_path} (one-time setup)…",
        file=sys.stderr,
    )
    SentenceTransformer(model_id).save(str(local_path))
    print(f"✓  model saved to {local_path}", file=sys.stderr)
    return str(local_path)
