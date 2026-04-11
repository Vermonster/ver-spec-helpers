# spec-contextualize

Skills to help agents load only the specs relevant to a task, and keep a growing spec library healthy over time.

As a spec library grows, loading all of them into an agent's context window becomes a liability — noise accumulates, performance degrades, and relevance drops. These two skills fix that. They work with any project that stores specs as markdown files in a consistent directory structure — whether you use [OpenSpec](https://github.com/openspec), [Spec Kit](https://github.com/github/spec-kit), or your own convention.

```bash
npx skills add Vermonster/spec-contextualize
```

---

## Skills

### `ver-spec-context` — Focused Context Loading

Load only the specs your current task actually needs.

At the start of any spec-driven task, this skill reads a compact auto-generated `index.yaml` — a terse catalog of every spec with a one-sentence summary, token estimate, domain tag, and referenced code paths — then selects only the specs relevant to the work at hand. Everything else stays off the context window.

**What it does:**
1. Locates the specs directory (`openspec/specs/`, `specs/`, or any directory containing `spec.md` files)
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

### Signaling to agents

Installing the skills makes them available, but adding a note to your repo's agent instructions file ensures agents reach for `ver-spec-context` proactively — before starting any spec-driven task — rather than only when explicitly asked.

Add a line to whichever file your agent runtime reads:

| Runtime | File |
|---|---|
| Claude / Codex / most agents | `AGENTS.md` |
| Claude (project-level) | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cursor | `.cursorrules` |

Suggested wording:

```markdown
Before starting any task that involves specs, invoke the `ver-spec-context` skill
to load only the specs relevant to the work at hand.
```

`ver-spec-health` does not need this — it is always invoked explicitly.

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

`index.yaml` is **never edited by hand** — it is generated and refreshed automatically by the skills or via the `bin/spec-index` CLI (installed separately, see below). Commit it alongside your specs so agents always have a starting point without rebuilding.

---

## CLI: `bin/spec-index`

A portable shell script for deterministic index management. Zero dependencies — works on Mac, Linux, and BSD.

The CLI is **not bundled by `npx skills add`** — install it separately into your repo:

```bash
curl -fsSL https://raw.githubusercontent.com/Vermonster/spec-contextualize/main/bin/spec-index \
  -o bin/spec-index && chmod +x bin/spec-index
```

Commit it alongside your specs so the whole team and CI have access.

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

`<specs-dir>` is auto-detected if omitted (looks for `openspec/specs/`, then `specs/`, then any directory containing `spec.md` files).

**Pre-commit hook example:**

```bash
# .git/hooks/pre-commit
bin/spec-index check || { echo "spec index is stale — run bin/spec-index build"; exit 1; }
```

---

## How These Skills Work With Your Specs

These skills work with any project that stores specs as individual markdown files in a consistent directory structure. The only hard requirement is `<specs-dir>/<spec-id>/spec.md`. Beyond that, summary extraction adapts to the format it detects.

When `spec-index build` runs, it walks the specs directory, extracts a one-line summary from each spec file, estimates token counts, infers domain tags from the spec ID, and produces `index.yaml`. Agents read this compact index first — then load only the individual spec files that are relevant to the task.

### With OpenSpec

[OpenSpec](https://github.com/openspec) stores specs under `openspec/specs/<spec-id>/spec.md`. Each spec opens with a 1–3 sentence summary paragraph immediately after the `# Title` line, before the first `---` separator. The CLI extracts that paragraph verbatim as the index summary.

```
openspec/
  specs/
    auth-session/
      spec.md        ← summary extracted from paragraph before first ---
    payment-processing/
      spec.md
```

Auto-detected: `bin/spec-index` checks for `openspec/specs/` first.

### With Spec Kit

[Spec Kit](https://github.com/github/spec-kit) stores specs under `specs/<spec-id>/spec.md`. Each spec opens with a `# Feature Specification: <Name>` title followed by structured metadata and user stories — there is no free-form summary paragraph. The CLI detects this format automatically (by the `# Feature Specification:` heading) and builds the summary from the feature name plus the first plain-text sentence in the first User Story.

```
specs/
  002-deterministic-demo-runtime/
    spec.md        ← summary built from feature name + User Story 1
  003-scenario-tui/
    spec.md
```

Auto-detected: `bin/spec-index` falls back to `specs/` when `openspec/specs/` is absent.

### With a Custom Layout

Any structure matching `<specs-dir>/<spec-id>/spec.md` works. Pass the path explicitly if it is not auto-detected:

```bash
bin/spec-index build path/to/my-specs
```

Summary extraction falls back to the first non-blank text line after the title heading.

---

## Requirements

- Specs must follow the `<specs-dir>/<spec-id>/spec.md` directory structure
- No external dependencies beyond standard POSIX tools (`find`, `awk`, `grep`, `wc`)

---

## Reference

- Index schema and build algorithm: [`skills/shared/index-format.md`](skills/shared/index-format.md)
- Health analysis algorithms: [`skills/ver-spec-health/references/analysis-procedures.md`](skills/ver-spec-health/references/analysis-procedures.md)

