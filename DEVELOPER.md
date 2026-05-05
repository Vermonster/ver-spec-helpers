# Developer Guide

How to work on `ver-spec-helpers` locally: set up the environment, run each code
path, create test specs, and keep the two parallel implementations in sync.

---

## Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| Python ≥ 3.10 | Package + RAG scripts | [python.org](https://www.python.org/downloads/) |
| pipx | Isolated CLI installs | `pip install pipx` |
| hatchling | Build backend (pulled in automatically) | via pip |
| Node.js | `npx skills add` | [nodejs.org](https://nodejs.org) |

---

## Project layout

```
ver-spec-helpers/
  bin/
    spec-index            POSIX shell script — zero-dep YAML commands + rag-* shims
  rag/
    build.py              Standalone script (curl-install path)
    search.py             Standalone script (curl-install path)
    requirements.txt      Direct deps for the standalone path
  src/
    spec_helpers/
      cli.py              argparse entry point — all 7 commands
      indexer.py          YAML index logic (Python port of the shell commands)
      rag/
        build.py          Canonical chunk+embed source  ← keep in sync with rag/build.py
        search.py         Canonical vector search source ← keep in sync with rag/search.py
  skills/
    shared/
      index-format.md     Index schema reference (YAML + RAG)
    ver-spec-search/
      SKILL.md            Agent skill: load relevant specs
    ver-spec-maint/
      SKILL.md            Agent skill: audit spec library health
      references/
        analysis-procedures.md
  pyproject.toml          Package metadata + pipx entry point
  README.md
```

---

## Setup

```bash
git clone git@github.com:Vermonster/ver-spec-helpers.git
cd ver-spec-helpers
pip install -e ".[dev]"   # installs the package in editable mode + sentence-transformers + numpy
```

> **Editable install** (`-e`) makes `spec_helpers` importable from `src/` without reinstalling after every edit. It also puts `spec-index` on your `PATH` so you can run it directly.

If there is no `[dev]` extras group yet, a plain editable install works too:

```bash
pip install -e .
```

---

## Creating test specs

The CLI auto-detects `openspec/specs/` or `specs/`. Create a minimal fixture:

```bash
mkdir -p openspec/specs/auth-session
cat > openspec/specs/auth-session/spec.md << 'EOF'
# Auth Session

Session lifecycle invariants for the authentication layer.

---

## Key Invariants

- `getSession()` returns null for expired tokens
- `getCurrentUser()` throws if called before `authenticate()`
EOF

mkdir -p openspec/specs/payment-processing
cat > openspec/specs/payment-processing/spec.md << 'EOF'
# Payment Processing

Rules governing payment capture and refund flows.

---

## Key Invariants

- Capture must follow authorisation within 7 days
- Partial refunds require an open order line
EOF
```

---

## Testing the shell script (`bin/spec-index`)

The shell script has zero dependencies and can be run directly:

```bash
# Build YAML index
bash bin/spec-index build openspec/specs

# Verify it's current
bash bin/spec-index check openspec/specs

# List all specs
bash bin/spec-index list openspec/specs

# Token budget breakdown
bash bin/spec-index stats openspec/specs
```

Run with `bash -x` to trace execution:

```bash
bash -x bin/spec-index build openspec/specs
```

### Testing rag-* commands via the shell script

The shell script's `rag-*` commands delegate to Python. They look for the scripts at
`$(dirname $0)/../rag/build.py` (source repo layout) and fall back to
`$(dirname $0)/rag/build.py` (flat install layout). From the repo root:

```bash
# These call rag/build.py and rag/search.py via the find_rag_script() helper
bash bin/spec-index rag-build openspec/specs
bash bin/spec-index rag-search "session expiry" openspec/specs
bash bin/spec-index rag-check openspec/specs
```

---

## Testing the Python package (`spec-index`)

After `pip install -e .`, the `spec-index` command runs from `src/spec_helpers/cli.py`:

```bash
# YAML commands
spec-index build   openspec/specs
spec-index check   openspec/specs
spec-index list    openspec/specs
spec-index stats   openspec/specs

# RAG commands
spec-index rag-build  openspec/specs          # ~30 s first run (model download); ~2 s after
spec-index rag-check  openspec/specs
spec-index rag-search "session expiry" openspec/specs
spec-index rag-search "refund rules"   openspec/specs -k 3
```

You can also invoke the rag modules directly for quick iteration:

```bash
python src/spec_helpers/rag/build.py  openspec/specs
python src/spec_helpers/rag/search.py openspec/specs "session expiry"
```

### Testing the standalone scripts (curl-install path)

```bash
# Requires: pip install sentence-transformers numpy  (or pip install -e .)
python rag/build.py  openspec/specs
python rag/search.py openspec/specs "session expiry"
```

---

## Testing the pipx install end-to-end

To test exactly what a user gets from `pipx install git+https://...`:

```bash
# Install from local source
pipx install .

# Now spec-index runs from the pipx-managed venv, not your local pip install
spec-index build openspec/specs
spec-index rag-build openspec/specs
spec-index rag-search "payment capture"

# Uninstall when done
pipx uninstall ver-spec-helpers
```

---

## Checking search quality

After `rag-build`, spot-check retrieval manually with queries that should and
shouldn't match each spec:

```bash
# Should return auth-session with high score
spec-index rag-search "token expiry behaviour"

# Should return payment-processing with high score
spec-index rag-search "refund partial order"

# Should return low scores for everything (no match)
spec-index rag-search "database migration strategy"
```

A useful pattern is to pipe the JSON through `jq` to focus on scores and spec IDs:

```bash
spec-index rag-search "session expiry" | jq '[.[] | {spec_id, score}]'
```

---

## Keeping the two RAG implementations in sync

There are two copies of the chunk+embed and search logic:

| Canonical (package) | Standalone (curl path) |
|---|---|
| `src/spec_helpers/rag/build.py` | `rag/build.py` |
| `src/spec_helpers/rag/search.py` | `rag/search.py` |

The standalone scripts are kept for users who prefer the curl-install path and
do not want the Python package. **Any logic change must be applied to both files.**

The docstring at the top of each standalone script notes this explicitly. A quick
diff catches drift:

```bash
diff <(grep -v '^#\|^"""' src/spec_helpers/rag/build.py) \
     <(grep -v '^#\|^"""' rag/build.py)

diff <(grep -v '^#\|^"""' src/spec_helpers/rag/search.py) \
     <(grep -v '^#\|^"""' rag/search.py)
```

---

## YAML index parity: shell vs Python

`src/spec_helpers/indexer.py` is a Python port of the `build`, `check`, `list`,
and `stats` commands in `bin/spec-index`. They must produce identical `index.yaml`
output for the same input.

To verify parity, build with both and diff:

```bash
spec-index build openspec/specs
cp openspec/specs/index.yaml /tmp/python-index.yaml

bash bin/spec-index build openspec/specs
diff /tmp/python-index.yaml openspec/specs/index.yaml
```

The only expected difference is `generated_at` (timestamp). Field values,
ordering, and quoting must match.

---

## Adding a new command

1. **Shell script** — add a `cmd_<name>()` function in `bin/spec-index` and a
   case entry in the dispatch block at the bottom.

2. **Python package** — add a subparser in `build_parser()` in `cli.py`, then
   handle `args.command == "<name>"` in `main()`. Put non-trivial logic in
   `indexer.py` (for YAML commands) or `src/spec_helpers/rag/` (for RAG commands).

3. **Update `usage()` in `bin/spec-index`** — keep the help text in sync with
   `build_parser()`.

4. **Update the README CLI reference table** in the *How It Works* section.

---

## Changing the embedding model

The model is controlled by the `SPEC_RAG_MODEL` environment variable (default:
`sentence-transformers/all-MiniLM-L6-v2`). To test a different model:

```bash
SPEC_RAG_MODEL=sentence-transformers/all-mpnet-base-v2 spec-index rag-build openspec/specs
spec-index rag-search "session expiry" openspec/specs
```

The model ID is stored in `manifest.json` at build time. `rag-search` and
`rag-check` always read the model from the manifest, so build and search
are guaranteed to use the same model even if the env var changes between runs.

---

## CI / pre-commit hooks

To fail CI when the YAML index is out of date:

```bash
# .github/workflows/ci.yml
- run: spec-index check openspec/specs
```

For the RAG index (optional — the embeddings are expensive to rebuild in CI):

```bash
- run: spec-index rag-check openspec/specs
```

As a pre-commit hook, create `.git/hooks/pre-commit`:

```bash
#!/usr/bin/env bash
set -e
spec-index check openspec/specs
```

---

## Gitignore recommendations

```gitignore
# RAG embeddings — binary, always regenerated from source
rag/embeddings.npy
openspec/specs/rag/embeddings.npy
specs/rag/embeddings.npy

# Optional: commit chunks.jsonl and manifest.json to let teammates
# skip the first rag-build. If you prefer not to commit them:
# openspec/specs/rag/
```
