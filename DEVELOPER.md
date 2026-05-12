# Developer Guide

How to work on `ver-spec-helpers` locally: set up the environment, run the CLI, create test fixtures, and verify shell/Python parity.

---

## Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| Python ≥ 3.10 | Package CLI | [python.org](https://www.python.org/downloads/) |
| pipx | Isolated CLI installs | `pip install pipx` |
| Node.js | `npx skills add` | [nodejs.org](https://nodejs.org) |

---

## Project layout

```
ver-spec-helpers/
  bin/
    spec-index          POSIX shell script — zero-dep, all commands except eval
  src/
    spec_helpers/
      __init__.py
      cli.py            argparse entry point — all 6 commands
      indexer.py        index build/check/list/stats/eval/coverage + parsing helpers
  skills/
    shared/
      index-format.md   Index schema and build algorithm reference
    ver-spec-search/
      SKILL.md          Agent skill: load relevant specs
    ver-spec-maint/
      SKILL.md          Agent skill: audit spec library health
      references/
        analysis-procedures.md
  pyproject.toml        Package metadata + pipx entry point (no runtime dependencies)
  Makefile              install / install-dev / reinstall / uninstall
  README.md
  DEVELOPER.md
```

---

## Setup

```bash
git clone git@github.com:Vermonster/ver-spec-helpers.git
cd ver-spec-helpers
pip install -e .
```

The editable install makes `spec_helpers` importable from `src/` without reinstalling after each edit, and puts `spec-index` on `PATH`.

---

## Creating test specs

`spec-index` auto-detects `openspec/specs/` or `specs/`. Create a minimal fixture to test against:

```bash
mkdir -p openspec/specs/auth-session openspec/specs/payment-processing

cat > openspec/specs/auth-session/spec.md << 'EOF'
# Auth Session

Session lifecycle invariants for the authentication layer.

---

## Key Invariants

- `getSession()` returns null for expired tokens
- `getCurrentUser()` throws if called before `authenticate()`

## Error States

- `SessionExpiredError` is raised on access after timeout
- See `auth-token` for token renewal rules
EOF

cat > openspec/specs/payment-processing/spec.md << 'EOF'
# Payment Processing

Rules governing payment capture and refund flows.

---

## Capture Rules

- `capturePayment()` must be called within 7 days of authorisation

## Refund Rules

- `issueRefund()` requires an open order line
EOF
```

---

## Testing the shell script (`bin/spec-index`)

The shell script has zero dependencies and can be run directly:

```bash
bash bin/spec-index build    openspec/specs
bash bin/spec-index check    openspec/specs
bash bin/spec-index list     openspec/specs
bash bin/spec-index stats    openspec/specs
bash bin/spec-index coverage openspec/specs
```

Run with `bash -x` to trace execution:

```bash
bash -x bin/spec-index build openspec/specs
```

---

## Testing the Python package (`spec-index`)

After `pip install -e .`, all six commands are available:

```bash
spec-index build    openspec/specs
spec-index check    openspec/specs
spec-index list     openspec/specs
spec-index stats    openspec/specs
spec-index coverage openspec/specs
spec-index eval "fix the token expiry bug in getSession" openspec/specs
spec-index eval "refund partial order" openspec/specs --budget 2000
```

---

## Evaluating index quality

`eval` simulates what `ver-spec-search` would select for a given task description and shows the scoring breakdown. Use it to verify that your specs have enough signal to be selected correctly.

```bash
# Should select auth-session with high score
spec-index eval "fix the token expiry bug in getSession"

# Should select payment-processing with high score
spec-index eval "implement partial refund for open orders"

# Should select nothing (no match)
spec-index eval "database migration strategy"
```

`coverage` shows which specs are missing signals:

```bash
spec-index coverage openspec/specs
```

A spec with no `symbols` won't match queries that mention function names. A spec with no `headings` loses the structural signal. Both are fixable by improving the spec source — add backtick-quoted identifiers and `##` sections, then rebuild the index.

---

## Testing the pipx install end-to-end

```bash
pipx install .

spec-index build    openspec/specs
spec-index eval "session expiry" openspec/specs
spec-index coverage openspec/specs

pipx uninstall ver-spec-helpers
```

---

## Shell vs Python parity (`build` command)

`src/spec_helpers/indexer.py` is a Python port of the shell `build` command. Both must produce identical `index.yaml` output for the same input (only `generated_at` differs).

To verify:

```bash
spec-index build openspec/specs
cp openspec/specs/index.yaml /tmp/python-index.yaml

bash bin/spec-index build openspec/specs
diff /tmp/python-index.yaml openspec/specs/index.yaml
```

---

## Adding a new command

1. **Shell script** — add a `cmd_<name>()` function in `bin/spec-index` and a case entry in the dispatch block.
2. **Python package** — add a subparser in `build_parser()` in `cli.py`, handle it in `main()`, and put the logic in `indexer.py`.
3. **Keep `usage()` in sync** with `build_parser()`.
4. **Update the README CLI reference table**.

---

## CI / pre-commit

Fail CI when the index is out of date:

```yaml
# .github/workflows/ci.yml
- run: spec-index check openspec/specs
```

As a pre-commit hook:

```bash
#!/usr/bin/env bash
set -e
spec-index check openspec/specs
```
