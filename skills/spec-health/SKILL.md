---
name: spec-health
description: Audit spec library health — find stale specs, overlapping content, and context bloat. Runs in analysis mode by default; write mode applies approved changes. Use periodically as a maintenance task or when specs feel unwieldy.
license: MIT
compatibility: Works with any project that has spec files in a consistent directory structure. Framework-agnostic.
metadata:
  version: "1.0.0"
---

Audit the health of a spec library and optionally apply improvements. Produces a structured report covering relevance drift, content overlap, context bloat, and index currency. Changes are never applied without explicit user approval.

**Input**: None required. Optionally specify:
- `--write` or "apply changes" to enter write mode after analysis
- A subset of spec IDs to focus on
- A path to the specs directory if it can't be auto-detected

---

## Modes

**Analysis mode** (default): Read-only. Produces a health report. No files are modified.

**Write mode**: Presents the analysis report first, then asks the user to confirm each category of changes before applying any. Write mode is only entered when the user explicitly requests it (e.g., "apply the recommendations", "fix the stale specs", or `--write` flag).

---

## Steps

### 1. Locate the Specs Directory

Look for spec files in this order:
1. `openspec/specs/` at the repo root
2. `specs/` at the repo root
3. Any directory containing multiple `spec.md` files

Set `<specs_dir>` to the located path. If not found, report and stop.

### 2. Inventory Specs

```bash
find <specs_dir> -name "spec.md" | sort
```

Build the list of all spec IDs (directory names). Note total count.

### 3. Ensure Index Is Current

Check `<specs_dir>/index.yaml` freshness per [shared/index-format.md](../shared/index-format.md). Rebuild if stale. The index provides token estimates and path references for all three analyses.

### 4. Run the Three Analyses

Run all three analyses. Use subagents if the spec count is large (>20 specs) to preserve context.

See [references/analysis-procedures.md](references/analysis-procedures.md) for detailed algorithms.

#### Analysis A: Relevance Drift

For each spec, extract code path references (from the index `paths` field, or re-parse the spec if the index is missing them). For each referenced path:

```bash
test -e <path> && echo "exists" || echo "missing"
```

Flag a spec as **drifted** if more than half its referenced paths no longer exist.
Flag a spec as **partially drifted** if 1–50% of its paths are missing.

#### Analysis B: Content Overlap

For each pair of specs:
1. Extract the set of h2/h3 headings from each spec
2. Compute the overlap ratio: `shared_headings / min(headings_a, headings_b)`
3. Flag pairs with overlap ratio ≥ 0.5 as **overlap candidates**

Also flag specs whose `summary` shares ≥ 4 significant words with another spec's summary (after removing stop words).

#### Analysis C: Context Bloat

Using `token_estimate` from the index:
1. Rank specs by size (largest first)
2. Compute total token budget across all specs
3. Flag any spec whose `token_estimate` exceeds 800 as **oversized** (likely a consolidation or SUMMARIZE candidate)
4. Note the cumulative token total and what percentage the top 3 specs consume

### 5. Produce the Health Report

Output the full analysis in this structure:

---

```
## Spec Health Report

**Specs directory**: <specs_dir>
**Total specs**: N  |  **Total tokens (est.)**: ~X

---

### A. Relevance Drift

| Spec | Status | Missing Paths |
|------|--------|---------------|
| spec-id | 🔴 Drifted | lib/old-module/, services/gone/ |
| spec-id | 🟡 Partial | lib/moved-file.ts |
| spec-id | ✅ Current | — |

**Recommendation**: [remove / update paths in] the drifted specs.

---

### B. Content Overlap

| Spec A | Spec B | Overlap | Shared Headings |
|--------|--------|---------|-----------------|
| spec-a | spec-b | 67% | Key Invariants, Schema, Service Functions |

**Recommendation**: Consider consolidating spec-a and spec-b.

---

### C. Context Bloat

| Spec | Token Est. | Flag |
|------|-----------|------|
| spec-id | 820 | ⚠️ Oversized |
| spec-id | 450 | — |

**Top 3 specs consume X% of total token budget.**
**Total**: ~X tokens across N specs.

---

### D. Index Currency

Index status: ✅ Current  /  ⚠️ Stale (rebuilt during this run)  /  🔴 Missing (built during this run)

---

### Summary

- 🔴 N specs fully drifted (removal candidates)
- 🟡 N specs partially drifted (path updates needed)
- ⚠️ N overlap pairs (consolidation candidates)
- ⚠️ N oversized specs
- ✅ N specs healthy
```

---

### 6. Offer Write Mode

After presenting the report, always ask:

```
Would you like me to apply any of these recommendations?

1. Remove fully drifted specs (N specs)
2. Update partially drifted specs (N specs — remove dead path references)
3. Flag overlap pairs for consolidation (opens a consolidation workflow)
4. All of the above
5. Skip — analysis only

Reply with a number or describe what you'd like to address.
```

If the user selects nothing or says "no", stop here.

---

### 7. Write Mode — Apply Changes (with confirmation per category)

For each approved category, confirm the specific changes before applying:

#### Removing Drifted Specs

```
About to remove the following spec directories:
  - <specs_dir>/spec-id-one/
  - <specs_dir>/spec-id-two/

Confirm? (yes / no / show me spec-id-one first)
```

On confirmation, remove the directories and update `index.yaml`.

#### Updating Partially Drifted Specs

For each partially drifted spec, show the specific dead path references to be removed from the spec body:

```
In spec-id: removing references to:
  - `lib/old-path/` (line 12)
  - `services/gone/` (line 34)

Confirm? (yes / no / skip this spec)
```

Apply the edit, then rebuild the index entry.

#### Consolidation Workflow

For each flagged overlap pair, offer to:
1. Show both specs side by side for human review
2. Draft a consolidated spec (merged content, deduped invariants)
3. Apply the consolidated spec and remove the originals (requires explicit confirmation)

Consolidation is higher-risk than removal — always show the draft before writing.

#### After All Changes

Rebuild `index.yaml` to reflect the updated spec set.

Report:
```
## Changes Applied

- Removed N specs
- Updated N specs (dead path references cleaned)
- Consolidated N spec pairs → N new specs
- Index rebuilt: <specs_dir>/index.yaml
```

---

## Guardrails

- **Never remove or modify spec files without explicit user confirmation** — analysis mode is always safe
- Always run and present the full analysis before offering write mode
- For consolidations, always show a draft before applying — consolidation is lossy and must be human-reviewed
- Overlap detection flags *candidates*, not certainties — present reasoning, don't assert consolidation is correct
- If a spec has no `paths` references, skip relevance drift analysis for that spec (not enough signal) — note it as "no path references"
- Rebuild `index.yaml` after any write operation
- Use subagents for large spec sets to avoid exhausting the context window during analysis
