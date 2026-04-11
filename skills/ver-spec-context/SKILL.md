---
name: ver-spec-context
description: Load only the specs relevant to your current task. Use at the start of any task where project specs exist — reads a compact index to select and load only what's needed, rather than loading all specs.
license: MIT
compatibility: Works with any project that has spec files in a consistent directory structure. Framework-agnostic.
metadata:
  version: "1.0.0"
---

Load relevant specs for the current task by reading a compact index rather than all spec files.

**The problem this solves**: As a spec library grows, loading every spec at task start floods the context window with irrelevant content and degrades performance. This skill loads only what matters for the task at hand.

**Input**: A description of the current task. Optionally, an explicit list of spec IDs to include or exclude.

---

## Steps

### 1. Locate the Specs Directory

Look for spec files in this order:
1. An `openspec/specs/` directory at the repo root
2. A `specs/` directory at the repo root
3. Any directory containing multiple `spec.md` files

If none is found, inform the user and stop — this skill requires a structured specs directory.

Set `<specs_dir>` to the located path.

### 2. Check Index Freshness

**Preferred**: If `spec-index` is available in `PATH` or at `bin/spec-index` from the repo root, use it:
```bash
spec-index check <specs_dir>   # exits 0 if current, exits 1 if stale/missing
```

**Fallback** (agent-native check): Read `<specs_dir>/index.yaml` if it exists and determine if it is stale:
- File does not exist
- Any `spec.md` has a modification time newer than the index's `generated_at` timestamp:
  ```bash
  find <specs_dir> -name "spec.md" -newer <specs_dir>/index.yaml
  ```
- Spec file count differs from index entry count

If stale or missing, proceed to **Step 3**. Otherwise skip to **Step 4**.

### 3. Build the Index

**Preferred**: Run the CLI — it is faster and more reliable than agent-native building:
```bash
spec-index build <specs_dir>
```

**Fallback**: Generate `<specs_dir>/index.yaml` directly:

1. Discover specs: `find <specs_dir> -name "spec.md" | sort`
2. For each spec, extract:
   - **id**: directory name (`basename $(dirname <path>)`)
   - **summary**: detect format first:
     - If title line matches `^# Feature Specification:` (Spec Kit): use feature name + first plain-text sentence under `### User Story 1`, joined with ` — `
     - Otherwise (OpenSpec/custom): first non-blank text between the `# Title` line and the first `---`; max 200 chars
   - **token_estimate**: `wc -c < <path>` ÷ 4, rounded to nearest 10
   - **paths**: all backtick-quoted tokens containing `/` that don't start with `http`, deduplicated
   - **domain**: first hyphen-delimited word of the spec id (e.g. `auth-session` → `auth`)
3. Write `<specs_dir>/index.yaml` with `generated_at` set to current UTC time

Announce: "Building spec index…" and report how many specs were indexed on completion.

### 4. Read the Index

Read `<specs_dir>/index.yaml` in full. This file is small (typically <100 lines) and is the only spec-related file that must always be loaded.

### 5. Select Relevant Specs

Given the task description, select specs to load using these criteria, in priority order:

1. **Direct path overlap**: specs whose `paths` entries match files being modified or referenced in the task
2. **Domain match**: specs whose `domain` matches the task's functional area
3. **Keyword match**: specs whose `summary` or `id` contains key terms from the task description
4. **Foundation specs**: specs with `domain: infra` or `domain: auth` are often cross-cutting — include if the task touches authentication, tenancy, or infrastructure patterns

**Context budget**: aim to load specs totaling ≤ 4,000 `token_estimate`. If the relevant set exceeds this, prefer higher-priority matches and note what was excluded.

### 6. Load Selected Specs

Read each selected spec file at `<specs_dir>/<id>/spec.md`.

### 7. Report What Was Loaded (and What Wasn't)

```
## Spec Context Loaded

Loaded N specs (~X tokens):
- spec-id-one — <summary>
- spec-id-two — <summary>

Not loaded (M specs available):
- spec-id-three [domain: X] — <summary>  ← excluded: unrelated domain
- …

To load additional specs: ask me to "also load <spec-id>".
```

---

## Guardrails

- Always read the index before selecting specs — never load all specs without checking the index first
- If the task description is vague, load index only and ask the user to clarify the task domain before loading spec files
- If a user explicitly names a spec, load it regardless of relevance scoring
- Do not regenerate the index on every invocation — only when stale
- Never modify spec files — this skill is read-only
- If `index.yaml` generation fails (e.g., no spec.md files found), report clearly and do not silently proceed with an empty context
