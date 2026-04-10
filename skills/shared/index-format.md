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
    summary: <single sentence extracted from spec opening paragraph>
    token_estimate: <integer>
    paths:
      - <referenced code path>
```

### Field Definitions

| Field | Source | Notes |
|---|---|---|
| `id` | Directory name | Matches `specs/<id>/spec.md` |
| `domain` | Inferred from id prefix or paths | See domain inference rules below |
| `summary` | First paragraph of spec (between title and `---`) | Max 1-2 sentences. Strip markdown formatting. |
| `token_estimate` | `(character_count / 4)` rounded to nearest 10 | Rough guide for context budgeting |
| `paths` | Backtick-quoted strings in spec body containing `/` | Deduplicated; skip single-segment tokens |

### Domain Inference Rules

Infer domain from the spec `id` prefix in this order:

1. **Exact prefix match** on known patterns: `census-` → `census`, `ehr-` → `ehr`, `clinical-` → `clinical`, `auth-` / `identity-` / `tenant-` → `auth`, `encounter-` → `encounter`, `charge-` → `billing`, `cdk-` / `ecs-` / `container-` / `image-` → `infra`, `dev-` / `test-` / `integration-` → `dx`, `ui-` → `ui`
2. **First path segment** of most-referenced `paths` entry (e.g., `services/census/` → `census`)
3. **First hyphen-delimited word** of the spec id as fallback

---

## Build Procedure

Agents follow this procedure to generate or refresh `index.yaml`:

1. **Discover spec files**
   ```bash
   find <specs_dir> -name "spec.md" | sort
   ```

2. **For each spec file**, extract:
   - **id**: the directory name containing the spec (`basename $(dirname <path>)`)
   - **title line**: first line matching `^# `
   - **summary**: all non-empty lines between the title line and the first `---` separator, joined and stripped of markdown formatting (backticks, bold, links). Trim to ≤200 characters.
   - **token_estimate**: `wc -c < <path>` divided by 4, rounded to nearest 10
   - **paths**: all backtick-quoted tokens containing `/` that don't start with `http`, deduplicated

3. **Infer domain** using the rules above

4. **Write `index.yaml`** to `<specs_dir>/index.yaml` with `generated_at` set to current UTC time

### Staleness Check

The index is considered stale if:
- `index.yaml` does not exist
- Any `spec.md` file has a modification time newer than `generated_at`
- The count of `spec.md` files differs from the count of entries in the index

When stale, regenerate before proceeding.
