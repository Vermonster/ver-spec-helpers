# ver-spec-helpers

Skills to help agents load only the specs relevant to a task, and keep a growing spec library healthy over time.

As a spec library grows, loading every spec floods the context window with irrelevant content and degrades performance. These skills fix that — compatible with [OpenSpec](https://github.com/openspec), [Spec Kit](https://github.com/github/spec-kit), or any `<specs-dir>/<spec-id>/spec.md` layout.

---

## Installation

```bash
npx skills add Vermonster/ver-spec-helpers
```

### Option A — pipx (recommended)

Installs `spec-index` globally with no external dependencies:

```bash
pipx install git+https://github.com/Vermonster/ver-spec-helpers
```

### Option B — shell script (zero dependencies)

```bash
curl -fsSL https://raw.githubusercontent.com/Vermonster/ver-spec-helpers/main/bin/spec-index \
  -o bin/spec-index && chmod +x bin/spec-index
```

The shell script supports all commands except `eval` (which requires the Python CLI).

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

Load only the specs your current task actually needs. Reads a compact auto-generated `index.yaml` and selects specs by matching the task description against symbols (function/class names), code paths, headings, domain, and summary keywords — targeting ≤ 4,000 tokens. Reports what was loaded and what was skipped.

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

### The index (`index.yaml`)

Every `spec-index build` run produces a single compact file at the root of the specs directory. It is the only file agents need to read before deciding which specs to load:

```yaml
generated_at: 2026-04-11T15:00:00Z
specs_dir: openspec/specs
specs:
  - id: auth-session
    domain: auth
    updated_at: 2026-03-14T10:22:00Z
    summary: "Session lifecycle invariants; getSession() returns null for expired tokens."
    token_estimate: 310
    paths:
      - lib/auth/
    symbols:
      - getSession()
      - getCurrentUser()
      - AuthSession
    headings:
      - Key Invariants
      - Error States
      - Token Lifecycle
    related:
      - auth-token
```

| Field | How it's produced |
|---|---|
| `id` | Directory name of the spec |
| `domain` | First hyphen-delimited word of the id (`auth-session` → `auth`) |
| `updated_at` | `git log -1 --format=%cI` on the spec file; omitted outside a git repo |
| `summary` | Extracted from the spec's opening paragraph; max 200 chars, markdown stripped |
| `token_estimate` | `file_bytes / 4`, rounded to the nearest 10 — rough context budget guide |
| `paths` | Backtick-quoted tokens containing `/` in the spec body |
| `symbols` | Backtick-quoted identifiers without `/` — function, class, and method names |
| `headings` | H2 and H3 headings from the spec body, in document order |
| `related` | Other spec IDs referenced verbatim anywhere in the spec body |

`index.yaml` is never edited by hand. Commit it alongside your specs.

---

### How `ver-spec-search` selects specs

The skill reads `index.yaml` and scores each spec against the task description using five signals, in priority order:

| Signal | Weight | Example match |
|---|---|---|
| Symbol match | 3.0 × hits | task mentions `getSession()`, spec has it in `symbols` |
| Path overlap | 2.0 × hits | task references `lib/auth/`, spec lists it in `paths` |
| Heading match | 1.5 × hits | task mentions "token expiry", spec has "Token Lifecycle" heading |
| Domain match | 1.0 | task is about auth, spec `domain` is `auth` |
| Summary keywords | 0.5 × words | shared significant words after stop-word removal |

Specs scoring above zero are ranked and loaded until the 4,000-token budget is filled. Specs in a selected spec's `related` list are considered as co-load candidates.

---

### CLI reference

`spec-index` is available as a POSIX shell script (`bin/spec-index`, zero dependencies) or as a Python package installed via pipx. The pipx version supports all commands; the shell script supports all except `eval`.

```bash
spec-index build    [<specs-dir>]              # parse specs → index.yaml
spec-index check    [<specs-dir>]              # exit 1 if stale (CI / pre-commit)
spec-index list     [<specs-dir>]              # print id, domain, summary
spec-index stats    [<specs-dir>]              # token budget + domain breakdown
spec-index coverage [<specs-dir>]              # signal richness per spec (symbols, headings…)
spec-index eval     "<query>" [<specs-dir>]    # score specs against a query; simulate selection
```

`<specs-dir>` is auto-detected if omitted (checks `openspec/specs/` then `specs/`).

---

## Reference

These files are part of the source repo and are not installed by `npx skills add`:

- Index schema and build algorithm: [`skills/shared/index-format.md`](skills/shared/index-format.md)
- Health analysis algorithms: [`skills/ver-spec-maint/references/analysis-procedures.md`](skills/ver-spec-maint/references/analysis-procedures.md)
