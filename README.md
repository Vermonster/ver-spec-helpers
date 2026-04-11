# spec-contextualize

Agent skills for managing spec library context as your [OpenSpec](https://github.com/openspec) library grows. As the number of specs increases, loading all of them into an agent's context window becomes a liability — noise accumulates, performance degrades, and relevance drops. These two skills fix that.

```bash
npx skills add Vermonster/spec-contextualize
```

---

## Skills

### `ver-spec-context` — Focused Context Loading

Load only the specs your current task actually needs.

At the start of any spec-driven task, this skill reads a compact auto-generated `index.yaml` — a terse catalog of every spec with a one-sentence summary, token estimate, domain tag, and referenced code paths — then selects only the specs relevant to the work at hand. Everything else stays off the context window.

**What it does:**
1. Locates the specs directory (`openspec/specs/`, `specs/`, or nearest equivalent)
2. Checks freshness of `index.yaml`; rebuilds it if stale
3. Reads the index (~100 lines regardless of spec library size)
4. Scores specs by path overlap, domain match, and keyword relevance
5. Loads the winning set (targeting ≤ 4,000 estimated tokens)
6. Reports what was loaded and what was intentionally skipped

**Invoke it with**: *"Load spec context for this task"* or just start a task — the skill is designed to run first.

---

### `ver-spec-health` — Spec Library Maintenance

Find and fix what's dragging your spec library down.

Runs a structured audit across three dimensions — relevance drift (specs whose referenced code no longer exists), content overlap (spec pairs covering the same territory), and context bloat (oversized specs consuming a disproportionate share of the token budget). Analysis mode is always read-only. Write mode presents findings and applies changes only after explicit confirmation per category.

**What it detects:**
- **Relevance drift** — specs referencing code paths that no longer exist
- **Content overlap** — spec pairs with ≥ 50% shared heading structure
- **Context bloat** — specs exceeding 800 estimated tokens; top-heavy distributions

**Invoke it with**: *"Run spec health"* or *"Audit my specs"* for analysis. Add *"and apply the recommendations"* or `--write` to enter write mode.

---

## Installation

```bash
npx skills add Vermonster/spec-contextualize
```

This installs both `ver-spec-context` and `ver-spec-health` into your project's agent skill directories (`.claude/skills/`, `.github/skills/`, `.cursor/skills/`, etc.).

To install a single skill:

```bash
npx skills add Vermonster/spec-contextualize --skill ver-spec-context
npx skills add Vermonster/spec-contextualize --skill ver-spec-health
```

To install globally (available across all projects):

```bash
npx skills add Vermonster/spec-contextualize --global
```

---

## The Index

Both skills share `index.yaml` — a small, auto-generated file at the root of your specs directory. It is the only file agents must always read; all spec files are loaded on demand from it.

```yaml
generated_at: 2026-04-11T15:00:00Z
specs_dir: openspec/specs
specs:
  - id: payment-processing
    domain: payment
    summary: "Payments table invariants; idempotency key semantics and retry behavior for failed charges."
    token_estimate: 420
    paths:
      - services/payments/
      - lib/db/schema/payments.ts
  - id: auth-session
    domain: auth
    summary: "Session lifecycle invariants; getSession() returns null for expired tokens, getCurrentUser() throws."
    token_estimate: 310
    paths:
      - lib/auth/
```

`index.yaml` is **never edited by hand** — it is generated and refreshed automatically by the skills or via the included CLI. Commit it alongside your specs so agents always have a starting point without rebuilding.

---

## CLI: `bin/spec-index`

A portable shell script for deterministic index management. Zero dependencies — works on Mac, Linux, and BSD.

```bash
# Build or rebuild the index
bin/spec-index build [<specs-dir>]

# Check freshness (exits 1 if stale — suitable for CI / pre-commit hooks)
bin/spec-index check [<specs-dir>]

# List all specs with domain and summary
bin/spec-index list [<specs-dir>]

# Show token budget and domain breakdown
bin/spec-index stats [<specs-dir>]
```

`<specs-dir>` is auto-detected if omitted (looks for `openspec/specs/` then `specs/`).

**Pre-commit hook example:**

```bash
# .git/hooks/pre-commit
bin/spec-index check || { echo "spec index is stale — run bin/spec-index build"; exit 1; }
```

---

## Requirements

- Specs must follow the `<specs-dir>/<spec-id>/spec.md` directory structure
- Each spec should open with a 1–3 sentence summary paragraph between the `# Title` line and the first `---` separator (the CLI and skills use this invariant to extract summaries)
- No external CLI dependencies beyond standard POSIX tools (`find`, `awk`, `grep`, `wc`)
- Compatible with [OpenSpec](https://github.com/openspec) conventions but not limited to them

---

## Related

- [`ver-spec-health`](skills/ver-spec-health/SKILL.md) complements rather than replaces quality-focused audit skills (e.g., `openspec-evaluate-specs`). Health targets efficiency — token load, structural staleness, and overlap. Evaluate targets content quality — retention policy, completeness, accuracy.
- Index schema and build algorithm reference: [`skills/shared/index-format.md`](skills/shared/index-format.md)
- Detailed analysis algorithms: [`skills/ver-spec-health/references/analysis-procedures.md`](skills/ver-spec-health/references/analysis-procedures.md)

