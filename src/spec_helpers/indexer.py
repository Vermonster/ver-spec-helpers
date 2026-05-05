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
