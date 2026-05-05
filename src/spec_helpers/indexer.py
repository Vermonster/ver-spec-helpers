"""
indexer.py — YAML index build/check/list/stats

Python port of the bin/spec-index shell commands (build, check, list, stats).
Behaviour is identical to the shell script; the two implementations should
stay in sync if the index format ever changes.
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

# ── constants ─────────────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "is", "are", "was", "be", "been",
    "for", "to", "of", "in", "on", "at", "by", "as", "it", "its",
    "not", "with", "from", "all", "can", "will", "when", "if", "has",
    "have", "do", "does", "that", "this", "these", "those",
})

# Scoring weights for eval
_WEIGHTS = {
    "symbols":  3.0,   # exact identifier name — most specific signal
    "paths":    2.0,   # code path reference
    "headings": 1.5,   # structural / topic signal
    "domain":   1.0,   # broad functional area
    "summary":  0.5,   # per matching keyword
}


# ── directory helpers ─────────────────────────────────────────────────────────


def detect_specs_dir() -> Path | None:
    for candidate in ["openspec/specs", "specs"]:
        p = Path(candidate)
        if p.is_dir() and any(p.rglob("spec.md")):
            return p
    return None


def require_specs_dir(path_arg: str | None) -> Path:
    if path_arg:
        p = Path(path_arg)
        if not p.is_dir():
            print(f"error: directory not found: {path_arg}", file=sys.stderr)
            sys.exit(1)
        return p
    detected = detect_specs_dir()
    if detected is None:
        print("error: could not find a specs directory.", file=sys.stderr)
        print(
            "       Pass one explicitly: spec-index <command> <specs-dir>",
            file=sys.stderr,
        )
        sys.exit(1)
    return detected


# ── text helpers ──────────────────────────────────────────────────────────────


def strip_markdown(text: str) -> str:
    text = re.sub(r"`", "", text)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*", "", text)
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", "", text)
    text = text.replace('"', "'")
    return text


def _yaml_scalar(s: str) -> str:
    """Quote a YAML scalar string if it contains special characters."""
    if any(c in s for c in ':#[]{},&*?|>!%@"\''):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _yaml_list(values: list[str], indent: str = "      ") -> list[str]:
    return [f"{indent}- {_yaml_scalar(v)}" for v in values]


# ── extraction helpers ────────────────────────────────────────────────────────


def extract_summary(text: str) -> str:
    lines = text.splitlines()

    if any(line.startswith("# Feature Specification:") for line in lines):
        feature_name = ""
        story_text = ""
        in_story = False
        for line in lines:
            if line.startswith("# Feature Specification:"):
                feature_name = line.removeprefix("# Feature Specification:").strip()
            if "### User Story 1" in line:
                in_story = True
                continue
            if in_story:
                if line.startswith("**"):
                    continue
                stripped = line.strip()
                if stripped and stripped[0].isalpha():
                    story_text = stripped
                    break
        summary = f"{feature_name} — {story_text}" if story_text else feature_name
        return strip_markdown(summary)[:200]

    found_title = False
    for line in lines:
        if re.match(r"^# ", line):
            found_title = True
            continue
        if found_title:
            if line.startswith("---") or line.startswith("#"):
                break
            stripped = line.strip()
            if stripped:
                return strip_markdown(stripped)[:200]

    return ""


def extract_paths(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for token in re.findall(r"`([^`]+/[^`]+)`", text):
        if token.startswith("http") or token.startswith("/"):
            continue
        if any(c in token for c in "?=*"):
            continue
        if token not in seen:
            seen.add(token)
            result.append(token)
    return sorted(result)


def extract_symbols(text: str) -> list[str]:
    """Backtick-quoted identifiers: function/class/method names (no slash)."""
    seen: set[str] = set()
    result: list[str] = []
    for token in re.findall(r"`([^`]+)`", text):
        if "/" in token or token.startswith("http"):
            continue
        if re.match(r"^\d+$", token) or len(token) < 2:
            continue
        if token not in seen:
            seen.add(token)
            result.append(token)
    return sorted(result)


def extract_headings(text: str) -> list[str]:
    """H2 and H3 headings from the spec body."""
    headings = []
    for line in text.splitlines():
        m = re.match(r"^#{2,3} (.+)", line)
        if m:
            headings.append(m.group(1).strip())
    return headings


def extract_related(text: str, all_ids: set[str], current_id: str) -> list[str]:
    """Other spec IDs explicitly referenced in this spec's body."""
    return sorted(
        sid for sid in all_ids
        if sid != current_id and re.search(r"\b" + re.escape(sid) + r"\b", text)
    )


def git_updated_at(spec_path: Path) -> str | None:
    """ISO 8601 timestamp of the last git commit touching this file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(spec_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        ts = result.stdout.strip()
        return ts if ts else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def token_estimate(spec_path: Path) -> int:
    chars = spec_path.stat().st_size
    return round((chars / 4) / 10) * 10


# ── commands ──────────────────────────────────────────────────────────────────




# ── index parsing ─────────────────────────────────────────────────────────────


def parse_index(specs_dir: Path) -> list[dict]:
    """Parse index.yaml into a list of spec dicts.

    No third-party YAML library required — the format is generated by
    cmd_build so the structure is fully known.
    """
    index_path = specs_dir / "index.yaml"
    if not index_path.exists():
        print(
            f"error: index.yaml not found — run: spec-index build {specs_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    specs: list[dict] = []
    current: dict | None = None
    current_list_field: str | None = None

    for line in index_path.read_text().splitlines():
        if line.startswith("  - id:"):
            if current:
                specs.append(current)
            current = {"id": line.split(":", 1)[1].strip()}
            current_list_field = None
        elif current is not None:
            if line.startswith("    ") and not line.startswith("      "):
                current_list_field = None
                key, _, val = line.strip().partition(":")
                val = val.strip().strip('"')
                if val == "[]":
                    current[key] = []
                elif val:
                    current[key] = val
                else:
                    current_list_field = key
                    current[key] = []
            elif line.startswith("      - ") and current_list_field:
                item = line.strip().lstrip("- ").strip('"')
                current[current_list_field].append(item)

    if current:
        specs.append(current)

    return specs


# ── eval / scoring ────────────────────────────────────────────────────────────


def _tokenise(text: str) -> set[str]:
    return {
        t for t in re.findall(r"\b\w+\b", text.lower())
        if t not in _STOP_WORDS and len(t) > 1
    }


def score_spec(query: str, spec: dict) -> tuple[float, list[str]]:
    """Score *spec* against *query*. Returns (score, human-readable reasons)."""
    tokens = _tokenise(query)
    score = 0.0
    reasons: list[str] = []

    sym_hits = [s for s in spec.get("symbols", []) if any(t in s.lower() for t in tokens)]
    if sym_hits:
        pts = len(sym_hits) * _WEIGHTS["symbols"]
        score += pts
        reasons.append(f"symbols({', '.join(sym_hits[:3])})+{pts:.0f}")

    path_hits = [p for p in spec.get("paths", []) if any(t in p.lower() for t in tokens)]
    if path_hits:
        pts = len(path_hits) * _WEIGHTS["paths"]
        score += pts
        reasons.append(f"paths({', '.join(path_hits[:2])})+{pts:.0f}")

    hdg_hits = [h for h in spec.get("headings", []) if any(t in h.lower() for t in tokens)]
    if hdg_hits:
        pts = len(hdg_hits) * _WEIGHTS["headings"]
        score += pts
        reasons.append(f"headings({', '.join(hdg_hits[:2])})+{pts:.1f}")

    domain = spec.get("domain", "")
    if domain and domain.lower() in tokens:
        score += _WEIGHTS["domain"]
        reasons.append(f"domain({domain})+1")

    summary_tokens = _tokenise(spec.get("summary", ""))
    kw_hits = tokens & summary_tokens
    if kw_hits:
        pts = len(kw_hits) * _WEIGHTS["summary"]
        score += pts
        reasons.append(f"summary({', '.join(sorted(kw_hits)[:4])})+{pts:.1f}")

    return score, reasons


def cmd_eval(specs_dir: Path, query: str, budget: int = 4000) -> None:
    specs = parse_index(specs_dir)
    scored = sorted(
        [(score_spec(query, s), s) for s in specs],
        key=lambda x: -x[0][0],
    )

    print(f'Query: "{query}"')
    print(f"Index: {specs_dir}/index.yaml  ({len(specs)} specs)\n")

    loaded: list[tuple] = []
    over_budget: list[tuple] = []
    no_match: list[dict] = []
    token_total = 0

    for (score, reasons), spec in scored:
        tokens = int(spec.get("token_estimate", 0))
        if score == 0:
            no_match.append(spec)
        elif token_total + tokens <= budget:
            loaded.append((score, reasons, spec, tokens))
            token_total += tokens
        else:
            over_budget.append((score, reasons, spec, tokens))

    col = 36

    print("WOULD LOAD:")
    if loaded:
        for score, reasons, spec, tokens in loaded:
            bar = "█" * min(round(score), 20)
            print(f"  {spec['id']:{col}} {score:5.1f}  {bar}")
            print(f"  {'':{col}}        {'  '.join(reasons)}")
            print()
    else:
        print("  (none matched)")
    print(f"  {'':-<60}")
    print(f"  total: ~{token_total} tokens of {budget} budget\n")

    if over_budget:
        print("MATCHED but over budget:")
        for score, reasons, spec, tokens in over_budget:
            print(f"  {spec['id']:{col}} {score:5.1f}  (~{tokens} tokens)")
            print(f"  {'':{col}}        {'  '.join(reasons)}")
            print()

    if no_match:
        print("NO MATCH:")
        for spec in no_match:
            print(f"  {spec['id']}")


def cmd_coverage(specs_dir: Path) -> None:
    specs = parse_index(specs_dir)
    warnings: list[str] = []

    print(f"Signal coverage: {specs_dir}/index.yaml  ({len(specs)} specs)\n")
    print(f"  {'ID':<36} {'sym':>4} {'hdg':>4} {'pth':>4} {'rel':>4}  summary")
    print(f"  {'-' * 70}")

    for spec in specs:
        sid = spec["id"]
        n_sym = len(spec.get("symbols", []))
        n_hdg = len(spec.get("headings", []))
        n_pth = len(spec.get("paths", []))
        n_rel = len(spec.get("related", []))
        summary = spec.get("summary", "")

        sym_flag = " " if n_sym else "⚠"
        hdg_flag = " " if n_hdg else "⚠"
        slen = f"{len(summary)}ch" if summary else "⚠ empty"

        print(f"  {sym_flag}{sid:<35} {n_sym:>4} {n_hdg:>4}{hdg_flag}{n_pth:>4} {n_rel:>4}  {slen}")

        if not n_sym:
            warnings.append(f"{sid}: no symbols — add backtick-quoted identifiers")
        if not n_hdg:
            warnings.append(f"{sid}: no headings — add ## or ### sections")
        if not summary:
            warnings.append(f"{sid}: empty summary — add an opening paragraph before the first ---")

    print()
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  ⚠  {w}")
    else:
        print("✓  all specs have symbols, headings, and summaries")

def cmd_build(specs_dir: Path) -> None:
    spec_files = sorted(specs_dir.rglob("spec.md"))
    if not spec_files:
        print(f"error: no spec.md files found in {specs_dir}", file=sys.stderr)
        sys.exit(1)

    all_ids = {f.parent.name for f in spec_files}
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    lines: list[str] = [
        "# Auto-generated by spec-index. Do not edit manually.",
        f"generated_at: {timestamp}",
        f"specs_dir: {specs_dir}",
        "specs:",
    ]

    for spec_path in spec_files:
        spec_id = spec_path.parent.name
        domain = spec_id.split("-")[0]
        text = spec_path.read_text(errors="ignore")

        summary = extract_summary(text)
        tokens = token_estimate(spec_path)
        updated_at = git_updated_at(spec_path)
        paths = extract_paths(text)
        symbols = extract_symbols(text)
        headings = extract_headings(text)
        related = extract_related(text, all_ids, spec_id)

        lines.append(f"  - id: {spec_id}")
        lines.append(f"    domain: {domain}")
        if updated_at:
            lines.append(f"    updated_at: {updated_at}")
        lines.append(f'    summary: "{summary}"')
        lines.append(f"    token_estimate: {tokens}")

        for field, values in [
            ("paths", paths),
            ("symbols", symbols),
            ("headings", headings),
            ("related", related),
        ]:
            if values:
                lines.append(f"    {field}:")
                lines.extend(_yaml_list(values))
            else:
                lines.append(f"    {field}: []")

    index_path = specs_dir / "index.yaml"
    index_path.write_text("\n".join(lines) + "\n")
    print(f"built {index_path} ({len(spec_files)} specs)")


def cmd_check(specs_dir: Path) -> None:
    index_path = specs_dir / "index.yaml"

    if not index_path.exists():
        print(
            f"stale: index.yaml does not exist (run: spec-index build {specs_dir})",
            file=sys.stderr,
        )
        sys.exit(1)

    spec_files = sorted(specs_dir.rglob("spec.md"))
    index_mtime = index_path.stat().st_mtime
    newer = [f for f in spec_files if f.stat().st_mtime > index_mtime]
    if newer:
        print(
            f"stale: {len(newer)} spec file(s) modified after index was built "
            f"(run: spec-index build {specs_dir})",
            file=sys.stderr,
        )
        sys.exit(1)

    index_text = index_path.read_text()
    index_count = index_text.count("\n  - id:")
    if len(spec_files) != index_count:
        print(
            f"stale: {len(spec_files)} spec files but {index_count} index entries "
            f"(run: spec-index build {specs_dir})",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"ok: index is current ({index_count} specs)")


def cmd_list(specs_dir: Path) -> None:
    index_path = specs_dir / "index.yaml"
    if not index_path.exists():
        print(
            f"error: index.yaml not found — run: spec-index build {specs_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    current_id = current_domain = ""
    for line in index_path.read_text().splitlines():
        if line.startswith("  - id:"):
            current_id = line.split(":", 1)[1].strip()
        elif line.startswith("    domain:"):
            current_domain = line.split(":", 1)[1].strip()
        elif line.startswith("    summary:"):
            summary = line.split(":", 1)[1].strip().strip('"')
            print(f"{current_id:<40} {current_domain:<16} {summary}")


def cmd_stats(specs_dir: Path) -> None:
    index_path = specs_dir / "index.yaml"
    if not index_path.exists():
        print(
            f"error: index.yaml not found — run: spec-index build {specs_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    text = index_path.read_text()
    total_specs = text.count("\n  - id:")
    total_tokens = sum(int(m) for m in re.findall(r"token_estimate: (\d+)", text))
    domains: dict[str, int] = {}
    for d in re.findall(r"domain: (\S+)", text):
        domains[d] = domains.get(d, 0) + 1

    spec_tokens: list[tuple[int, str]] = []
    current_id = ""
    for line in text.splitlines():
        if line.startswith("  - id:"):
            current_id = line.split(":", 1)[1].strip()
        elif line.startswith("    token_estimate:"):
            t = int(line.split(":", 1)[1].strip())
            spec_tokens.append((t, current_id))

    print(f"specs:        {total_specs}")
    print(f"tokens (est): ~{total_tokens}")
    print()
    print("by domain:")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {domain:<20} {count} specs")
    print()
    print("largest specs:")
    for tokens, spec_id in sorted(spec_tokens, reverse=True)[:5]:
        print(f"  {spec_id:<40} ~{tokens} tokens")
