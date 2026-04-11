# spec-contextualize

Skills to help agents load only the specs relevant to a task, and keep a growing spec library healthy over time.

As a spec library grows, loading every spec floods the context window with irrelevant content and degrades performance. These skills fix that — compatible with [OpenSpec](https://github.com/openspec), [Spec Kit](https://github.com/github/spec-kit), or any `<specs-dir>/<spec-id>/spec.md` layout.

---

## Installation

```bash
npx skills add Vermonster/spec-contextualize
```

```bash
# Also install the CLI into your repo (recommended)
curl -fsSL https://raw.githubusercontent.com/Vermonster/spec-contextualize/main/bin/spec-index \
  -o bin/spec-index && chmod +x bin/spec-index
```

To install globally or a single skill:

```bash
npx skills add Vermonster/spec-contextualize --global
npx skills add Vermonster/spec-contextualize --skill ver-spec-context
```

### Signaling to agents

Add a line to your repo's agent instructions file so agents invoke `ver-spec-context` proactively at task start:

| Runtime | File |
|---|---|
| Claude / Codex / most agents | `AGENTS.md` |
| Claude (project-level) | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cursor | `.cursorrules` |

```markdown
Before starting any task that involves specs, invoke the `ver-spec-context` skill
to load only the specs relevant to the work at hand.
```

`ver-spec-health` does not need this — it is always invoked explicitly.

---

## Skills

### `ver-spec-context` — Focused Context Loading

Load only the specs your current task actually needs. Reads a compact auto-generated `index.yaml` to select relevant specs by path overlap, domain, and keyword match — targeting ≤ 4,000 tokens. Reports what was loaded and what was skipped.

**Invoke**: *"Load spec context for this task"* or just start a task.

### `ver-spec-health` — Spec Library Maintenance

Audit your spec library for:
- **Relevance drift** — specs referencing code paths that no longer exist
- **Content overlap** — spec pairs with ≥ 50% shared heading structure
- **Context bloat** — specs exceeding 800 estimated tokens

Analysis mode is always read-only. Write mode applies changes only after explicit confirmation per category.

**Invoke**: *"Run spec health"* or *"Audit my specs"*. Add *"and apply the recommendations"* for write mode.

---

## How It Works

Both skills share `index.yaml` — a small auto-generated file at the root of your specs directory. Agents read it first, then load only the individual spec files relevant to the task.

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

`index.yaml` is never edited by hand. Commit it alongside your specs.

### With OpenSpec

Specs live at `openspec/specs/<id>/spec.md`. The summary is extracted from the opening paragraph before the first `---`. Auto-detected first.

### With Spec Kit

Specs live at `specs/<id>/spec.md`. The summary is built from the `# Feature Specification:` title and the first plain-text sentence in User Story 1. Auto-detected as fallback.

### With a custom layout

Any `<specs-dir>/<id>/spec.md` structure works. Pass the path explicitly if not auto-detected:

```bash
bin/spec-index build path/to/my-specs
```

### CLI: `bin/spec-index`

A portable POSIX shell script for deterministic index management. Zero dependencies.

```bash
bin/spec-index build   # build or rebuild the index
bin/spec-index check   # exits 1 if stale — use in CI / pre-commit hooks
bin/spec-index list    # list all specs with domain and summary
bin/spec-index stats   # token budget and domain breakdown
```

---

## Reference

These files are part of the source repo and are not installed by `npx skills add`:

- Index schema and build algorithm: [`skills/shared/index-format.md`](skills/shared/index-format.md)
- Health analysis algorithms: [`skills/ver-spec-health/references/analysis-procedures.md`](skills/ver-spec-health/references/analysis-procedures.md)

