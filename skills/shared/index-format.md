# Spec Index Format

`index.yaml` is an auto-generated file placed at the root of the specs directory (e.g., `openspec/specs/index.yaml`). It is the primary discovery artifact for agents — a terse, structured catalog that enables loading only relevant specs rather than all of them.

**Never edit `index.yaml` by hand.** Regenerate it using the build procedure below whenever specs are added, removed, or significantly changed.

---

## Schema

```yaml
generated_at: <ISO 8601 timestamp>
specs_dir: <relative path to specs directory>
specs:
  - id: <spec directory name>
    domain: <inferred domain string>
    updated_at: <ISO 8601 timestamp of last git commit>
    summary: <single sentence extracted from spec opening paragraph>
    token_estimate: <integer>
    paths:
      - <referenced code path>
    symbols:
      - <referenced identifier>
    headings:
      - <h2 or h3 heading text>
    related:
      - <spec id cross-referenced in body>
```

### Field Definitions

| Field | Source | Notes |
|---|---|---|
| `id` | Directory name | Matches `specs/<id>/spec.md` |
| `domain` | Inferred from id prefix | First hyphen-delimited word (e.g. `auth-session` → `auth`) |
| `updated_at` | `git log -1 --format=%cI` on the spec file | Omitted if not in a git repo |
| `summary` | First paragraph of spec (between title and `---`) | Max 200 chars, markdown stripped |
| `token_estimate` | `(character_count / 4)` rounded to nearest 10 | Rough guide for context budgeting |
| `paths` | Backtick-quoted tokens containing `/` | Deduplicated; skip HTTP URLs and absolute paths |
| `symbols` | Backtick-quoted tokens without `/` | Function/class/method names; skip pure numbers and single chars |
| `headings` | H2 and H3 headings in spec body | Preserves order; useful for structural matching |
| `related` | Other spec IDs found verbatim in spec body | Cross-reference for co-loading linked specs |

```bash
spec-index rag-build [<specs-dir>]
```

This calls `rag/build.py`, which downloads the embedding model on first run (~90 MB, cached by `sentence-transformers` in `~/.cache`). Subsequent runs skip the download.

The RAG index is **not** rebuilt automatically by `ver-spec-search`. Rebuild it after adding or significantly changing specs, or add it to a pre-commit hook alongside `spec-index check`.

### Staleness check

```bash
spec-index rag-check [<specs-dir>]  # exits 0 if current, 1 if stale/missing
```

---

## Schema

---

## Build Procedure

Agents follow this procedure to generate or refresh `index.yaml`:

1. **Discover spec files**
   ```bash
   find <specs_dir> -name "spec.md" | sort
   ```

2. **Collect all spec IDs** (needed for `related` detection before processing individual specs)

3. **For each spec file**, extract:
   - **id**: the directory name containing the spec (`basename $(dirname <path>)`)
   - **domain**: first hyphen-delimited word of the id
   - **updated_at**: `git log -1 --format=%cI -- <path>`; omit field if empty or git unavailable
   - **summary**: extracted using format detection:
     - **Spec Kit format** (title starts with `# Feature Specification:`): feature name from the title + first plain-text sentence from `### User Story 1`, joined with ` — `
     - **OpenSpec / custom format**: first non-blank text between the `# Title` line and the first `---` separator; max 200 characters
   - **token_estimate**: `wc -c < <path>` divided by 4, rounded to nearest 10
   - **paths**: backtick-quoted tokens containing `/` that don’t start with `http` or `/`, no glob chars, deduplicated
   - **symbols**: backtick-quoted tokens *without* `/`, not starting with `http`, not pure numbers, length ≥ 2, deduplicated
   - **headings**: all lines matching `^#{2,3} `, text only, in document order
   - **related**: other spec IDs from the full set whose name appears verbatim (word-boundary match) in this spec’s body

4. **Write `index.yaml`** to `<specs_dir>/index.yaml` with `generated_at` set to current UTC time

### Staleness Check

The index is considered stale if:
- `index.yaml` does not exist
- Any `spec.md` file has a modification time newer than `generated_at`
- The count of `spec.md` files differs from the count of entries in the index

When stale, regenerate before proceeding.
