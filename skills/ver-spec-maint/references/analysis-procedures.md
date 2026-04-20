# Analysis Procedures

Detailed algorithms for the two core analyses in `spec-health`. These are implementation references for agents running the health audit.

---

## Relevance Drift Detection

**Goal**: Identify specs that describe code which no longer exists or has significantly moved.

### Step 1: Extract Path References

For each spec, collect path references from two sources:
1. The `paths` field in `index.yaml` (already extracted at index build time)
2. If `paths` is empty, re-parse the spec: extract all backtick-quoted tokens that contain `/` and do not start with `http`

### Step 2: Classify Each Path

For each path reference, test existence relative to the repo root:

```bash
# For a directory reference like `services/payments/`
test -d services/payments && echo "exists" || echo "missing"

# For a file reference like `lib/auth/session.ts`
test -f lib/auth/session.ts && echo "exists" || echo "missing"

# For an ambiguous reference, try both
test -e lib/auth && echo "exists" || echo "missing"
```

### Step 3: Score and Classify

| Missing ratio | Classification | Recommended action |
|---|---|---|
| > 50% paths missing | 🔴 Drifted | Remove spec (or major rewrite) |
| 1–50% paths missing | 🟡 Partial | Remove dead references from spec body |
| 0% paths missing | ✅ Current | No action |
| No paths found | ⚪ No signal | Note; skip drift scoring |

### Drift Signals Beyond Paths

In addition to explicit path checking, note these secondary signals (do not auto-classify, but include in report commentary):
- Spec references a package or library by name — check if it is still present in the project's dependency manifest (`package.json`, `Gemfile`, `pyproject.toml`, etc.)
- Spec references a specific schema table by name — check if a migration or model file for that table still exists
- Spec was last modified significantly earlier than related source files (use `git log --oneline -1 -- <spec>` vs `git log --oneline -1 -- <referenced_path>`)

---

## Content Overlap Detection

**Goal**: Find spec pairs that cover the same or substantially overlapping territory — consolidation candidates.

### Step 1: Extract Headings

For each spec, extract all h2 and h3 headings:

```bash
grep -E "^#{2,3} " <specs_dir>/<id>/spec.md | sed 's/^#* //'
```

Normalize headings: lowercase, strip punctuation, collapse whitespace.

### Step 2: Compute Pairwise Overlap

For each pair `(A, B)`:

```
headings_A = set of normalized headings from spec A
headings_B = set of normalized headings from spec B
shared     = headings_A ∩ headings_B
overlap    = |shared| / min(|headings_A|, |headings_B|)
```

Flag pairs where `overlap ≥ 0.5` (50% of the smaller spec's headings appear in the larger).

### Step 3: Summary-Level Overlap

As a secondary signal, compare spec summaries:

1. Tokenize each summary into words (lowercase, strip punctuation)
2. Remove stop words: `the, a, an, is, are, for, to, of, in, and, or, that, this, with, as, on, at, by`
3. Count shared significant words between each pair

Flag pairs with ≥ 4 shared significant words. This catches specs that describe overlapping concepts even if their section structure differs.

### Step 4: Domain-Scoped Comparison

Only compare pairs within the same `domain`. Cross-domain overlap is rarely meaningful and creates false positives (e.g., every spec has a "Key Invariants" section).

### Step 5: Presenting Overlap Candidates

For each flagged pair, include:
- Overlap ratio
- List of shared headings
- 1-sentence note on what territory seems duplicated

**Important**: Overlap is a signal, not a verdict. Two specs can legitimately share headings if they cover adjacent concepts at different layers (e.g., a schema spec and a service spec for the same feature). Always present candidates for human review.

---

## Consolidation Drafting

**Goal**: Produce a merged spec from two overlap candidates that preserves all unique invariants and eliminates duplication.

### Merging Rules

1. **Title**: Use the broader spec's title, or draft a new title that covers the combined scope
2. **ID**: Use the broader spec's ID, or propose a new ID if scope meaningfully changes
3. **Invariants**: Merge bullet lists by deduplication
   - Identical rules (after normalization): keep one instance
   - Contradictory rules: flag explicitly — do not silently drop either; present both for human resolution
   - Complementary rules: keep both, reorder for logical flow
4. **Paths**: Union of both `paths` sets, deduplicated
5. **Sections**: Use the superset of sections; merge content under matching headings
6. **Cross-references**: Remove any references between the two specs being merged (e.g., "see auth-token for details" when auth-token is the other spec being merged)
7. **Never invent**: Do not add new constraints, behavior, or context that doesn't exist in either source spec

### Normalization for Deduplication

Two invariant statements are considered duplicates if, after lowercasing and removing punctuation, they share ≥ 80% of their significant words (excluding stop words). When in doubt, keep both and note the similarity.

### Draft Output Format

```markdown
# <Merged Title>

<merged opening summary — 1–3 sentences covering the combined scope>

---

## <Section>

- <deduplicated invariants>

## <Section>

...
```

Append a `<!-- consolidation notes -->` block at the end of the draft (remove before finalizing):

```markdown
<!-- consolidation notes
Merged from: spec-a, spec-b
Dropped duplicates:
  - "X" (appeared in both)
Potential conflicts (needs human review):
  - spec-a says X; spec-b says Y
-->
```

---

## Context Bloat Assessment

**Goal**: Identify specs consuming disproportionate context budget.

### Metrics

| Metric | Threshold | Flag |
|---|---|---|
| Single spec token estimate | > 800 | ⚠️ Oversized |
| Top 3 specs as % of total | > 60% | ⚠️ Concentration |
| Total across all specs | > 8,000 | ⚠️ High total budget |

### Oversized Spec Diagnosis

For specs flagged as oversized, read the spec and diagnose the cause:

- **Scenario-heavy**: Still contains GIVEN/WHEN/THEN blocks or per-scenario descriptions → suggest consolidating to invariant bullet points
- **Implementation-heavy**: Describes library usage, file structure, imports → suggest removing (per SKIP tier)
- **Legitimately large**: Wide-scope cross-cutting spec with many invariants → may be a consolidation source (split into sub-specs by subdomain)
- **Duplication**: Repeats content found in a related spec → overlap candidate

Include diagnosis in the health report for each oversized spec.
