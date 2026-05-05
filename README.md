# ver-spec-helpers

Skills to help agents load only the specs relevant to a task, and keep a growing spec library healthy over time.

As a spec library grows, loading every spec floods the context window with irrelevant content and degrades performance. These skills fix that — compatible with [OpenSpec](https://github.com/openspec), [Spec Kit](https://github.com/github/spec-kit), or any `<specs-dir>/<spec-id>/spec.md` layout.

---

## Installation

```bash
npx skills add Vermonster/ver-spec-helpers
```

### Option A — pipx (recommended)

Installs `spec-index` globally in an isolated environment with all dependencies included:

```bash
pipx install git+https://github.com/Vermonster/ver-spec-helpers
```

Then build the RAG index once (downloads the embedding model ~90 MB on first run, cached after that):

```bash
spec-index rag-build
```

### Option B — shell script (zero dependencies)

Provides the YAML index commands only (`build`, `check`, `list`, `stats`). No Python or model required:

```bash
curl -fsSL https://raw.githubusercontent.com/Vermonster/ver-spec-helpers/main/bin/spec-index \
  -o bin/spec-index && chmod +x bin/spec-index
```

To add RAG support on top, also install the standalone scripts:

```bash
mkdir -p rag
curl -fsSL https://raw.githubusercontent.com/Vermonster/ver-spec-helpers/main/rag/build.py -o rag/build.py
curl -fsSL https://raw.githubusercontent.com/Vermonster/ver-spec-helpers/main/rag/search.py -o rag/search.py
pip install sentence-transformers numpy
bin/spec-index rag-build
```

> **Note:** Add `rag/embeddings.npy` to `.gitignore` (binary, regenerated from source). Committing `rag/chunks.jsonl` and `rag/manifest.json` is optional but lets teammates skip the first `rag-build`.

To install globally or a single skill:

```bash
npx skills add Vermonster/ver-spec-helpers --global
npx skills add Vermonster/ver-spec-helpers --skill ver-spec-search
```

### Signaling to agents

Add a line to your repo's agent instructions file so agents invoke `ver-spec-search` proactively at task start:

| Runtime | File |
|---|---|
| Claude / Codex / most agents | `AGENTS.md` |
| Claude (project-level) | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cursor | `.cursorrules` |

```markdown
Before starting any task that involves specs, invoke the `ver-spec-search` skill
to load only the specs relevant to the work at hand.
```

`ver-spec-maint` does not need this — it is always invoked explicitly.

---

## Skills

### `ver-spec-search` — Focused Context Loading

Load only the specs your current task actually needs. Reads a compact auto-generated `index.yaml` to select relevant specs by path overlap, domain, and keyword match — targeting ≤ 4,000 tokens. Reports what was loaded and what was skipped.

**Invoke**: *"Load spec context for this task"* or just start a task.

### `ver-spec-maint` — Spec Library Maintenance

Audit your spec library for:
- **Relevance drift** — specs referencing code paths that no longer exist
- **Content overlap** — spec pairs with ≥ 50% shared heading structure, prioritized by merge confidence
- **Context bloat** — specs exceeding 800 estimated tokens

Analysis mode is always read-only. Write mode applies changes only after explicit confirmation per category.

**Invoke**: *"Run spec health"* or *"Audit my specs"*. Add *"and apply the recommendations"* for write mode.

---

## How It Works

### Spec layout

Specs follow a simple directory convention — one folder per spec, one file inside:

```
<specs-dir>/
  auth-session/
    spec.md
  payment-processing/
    spec.md
  ...
```

Supported layouts are auto-detected:

| Layout | Path | Summary extraction |
|---|---|---|
| [OpenSpec](https://github.com/openspec) | `openspec/specs/<id>/spec.md` | First paragraph before the opening `---` |
| [Spec Kit](https://github.com/github/spec-kit) | `specs/<id>/spec.md` | `# Feature Specification:` title + first sentence of User Story 1 |
| Custom | any `<specs-dir>/<id>/spec.md` | Same as OpenSpec |

Pass the path explicitly if not auto-detected: `spec-index build path/to/my-specs`

---

### The YAML index (`index.yaml`)

Every `spec-index build` run produces a single compact file at the root of the specs directory. It is the only file agents need to read before deciding which specs to load:

```yaml
generated_at: 2026-04-11T15:00:00Z
specs_dir: openspec/specs
specs:
  - id: auth-session
    domain: auth
    summary: "Session lifecycle invariants; getSession() returns null for expired tokens, getCurrentUser() throws."
    token_estimate: 310
    paths:
      - lib/auth/
```

| Field | How it's produced |
|---|---|
| `id` | Directory name of the spec |
| `domain` | First hyphen-delimited word of the id (`auth-session` → `auth`) |
| `summary` | Extracted from the spec's opening paragraph; max 200 chars, markdown stripped |
| `token_estimate` | `file_bytes / 4`, rounded to the nearest 10 — rough context budget guide |
| `paths` | All backtick-quoted tokens containing `/` in the spec body; used for path-overlap matching |

`index.yaml` is never edited by hand. Commit it alongside your specs.

---

### The RAG index (`rag/`)

When built, the RAG index lives next to `index.yaml` and enables semantic search over spec content:

```
<specs-dir>/
  index.yaml          ← always present; keyword/domain metadata
  rag/
    chunks.jsonl      ← one JSON record per text chunk
    embeddings.npy    ← float32 matrix; rows match chunks.jsonl
    manifest.json     ← build metadata (model, chunk params, timestamps)
```

**Building the index** (`spec-index rag-build`):

1. Each `spec.md` is split into overlapping 900-character windows (150-char overlap) so long specs don't exceed embedding context limits and adjacent passages share context
2. Every chunk is embedded using [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — a fast, locally-run 80 MB model with no API calls
3. Vectors are L2-normalised before saving, so retrieval is a plain matrix dot-product (equivalent to cosine similarity but faster)
4. `manifest.json` records the model ID, chunk parameters, and spec count so `rag-check` can detect staleness without reading any embeddings

**Searching** (`spec-index rag-search "<query>"`):

1. The query is embedded with the same model recorded in `manifest.json`
2. A single NumPy matrix multiply scores all chunks simultaneously: `scores = embeddings @ query_vector`
3. The top-k chunks are returned as JSON to stdout; progress goes to stderr so output can be piped or parsed

```json
[
  {"score": 0.82, "spec_id": "auth-session", "path": "openspec/specs/auth-session/spec.md", "start": 0,   "text": "..."},
  {"score": 0.71, "spec_id": "auth-token",   "path": "openspec/specs/auth-token/spec.md",   "start": 750, "text": "..."}
]
```

> Add `rag/embeddings.npy` to `.gitignore` — it's a binary that's always regenerated from source. Committing `chunks.jsonl` and `manifest.json` is optional but lets teammates skip the first `rag-build`.

---

### How `ver-spec-search` selects specs

At task start the skill runs through up to three layers of evidence, stopping once the context budget (≤ 4,000 estimated tokens) is filled:

1. **Semantic search** — if the RAG index is current, embeds the task description and ranks specs by their highest-scoring chunk. Specs with a top-chunk score ≥ 0.4 are strong candidates; ≥ 0.6 are near-certain matches.
2. **Path overlap** — specs whose `paths` entries overlap files referenced in the task are promoted regardless of semantic score.
3. **Domain / keyword match** — specs whose `domain` or `summary` share key terms with the task description fill remaining budget.

When the RAG index is absent or stale, steps 2 and 3 run alone. This is the pre-RAG behaviour and still works well for small libraries.

---

### CLI reference

`spec-index` is available two ways: as a POSIX shell script (`bin/spec-index`, zero dependencies) or as a Python package installed via pipx. Both support all seven commands.

```bash
# YAML index
spec-index build   [<specs-dir>]          # parse specs → index.yaml
spec-index check   [<specs-dir>]          # exit 1 if stale (CI / pre-commit)
spec-index list    [<specs-dir>]          # print id, domain, summary
spec-index stats   [<specs-dir>]          # token budget + domain breakdown

# RAG index
spec-index rag-build  [<specs-dir>]          # chunk + embed → rag/
spec-index rag-search "<query>" [<specs-dir>] # semantic search → JSON on stdout
spec-index rag-check  [<specs-dir>]          # exit 1 if RAG index is stale
```

`<specs-dir>` is auto-detected if omitted (checks `openspec/specs/` then `specs/`).

---

## Reference

These files are part of the source repo and are not installed by `npx skills add`:

- Index schema and build algorithm: [`skills/shared/index-format.md`](skills/shared/index-format.md)
- Health analysis algorithms: [`skills/ver-spec-maint/references/analysis-procedures.md`](skills/ver-spec-maint/references/analysis-procedures.md)

