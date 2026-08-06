#!/usr/bin/env python3
"""Name and shame every JSON touchpoint in the repository.

The report is exhaustive over the checked-out tree. Authority-critical paths
fail closed. Boundary/import/export uses remain visible as quarantined debt so
new occurrences cannot arrive unnoticed.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PYTHON_SUFFIXES = {".py"}
SQL_SUFFIXES = {".sql"}
TEXT_SUFFIXES = {".sh", ".bash", ".yml", ".yaml", ".toml"}
SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
}

# Every execution-authority file is explicit. Adding an execution module without
# adding it here is itself reviewable debt; the architecture test mirrors this
# roster for a second independent gate.
AUTHORITY_FILES = {
    "src/nlp/spacy_adapter.py",
    "src/policy/binary_family_integrity_execution.py",
    "src/policy/carriers/canonical.py",
    "src/policy/no_json_checkpoint_execution.py",
    "src/policy/reference_backed_finalization.py",
    "src/policy/stage_budget_execution.py",
    "src/policy/streaming_spacy_parser_execution.py",
    "src/policy/typed_execution_callback_views.py",
    "src/pnf/streaming_build_reader.py",
    "src/runtime/durable_stage_state.py",
    "src/runtime/durable_work_item_hardening.py",
    "src/runtime/durable_work_items.py",
    "src/runtime/reference_receipt.py",
    "src/runtime/strict_postgres_execution.py",
    "src/storage/postgres/deterministic_admission_execution.py",
    "src/storage/postgres/distributed_semantic_execution.py",
    "src/storage/postgres/spacy_parser_model.py",
    "src/storage/postgres/spacy_parser_store.py",
    "src/storage/postgres/streaming_spacy_execution.py",
    "src/storage/postgres/typed_execution_pool.py",
    "src/storage/postgres/typed_value_store.py",
    "scripts/run_durable_coordinator_kill_probe.py",
    "scripts/run_post_closure_probe.py",
}
AUTHORITY_PREFIXES = tuple(
    f"database/postgres_migrations/{ordinal:03d}_"
    for ordinal in range(32, 40)
)

JSON_MODULES = {"json", "orjson", "ujson", "simplejson"}
JSON_CALLS = {
    "dump",
    "dumps",
    "load",
    "loads",
    "JSONEncoder",
    "JSONDecoder",
}
STRING_MARKERS = (
    ("::json", "sql_json_cast"),
    ("jsonb_build_", "sql_json_builder"),
    ("json_build_", "sql_json_builder"),
    (".jsonl", "jsonl_path"),
    ("application/json", "json_media_type"),
    ("canonical-json", "json_encoding_contract"),
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    category: str
    symbol: str
    snippet: str
    authority_violation: bool


def _is_authority(path: str) -> bool:
    return path in AUTHORITY_FILES or path.startswith(AUTHORITY_PREFIXES)


def _snippet(lines: list[str], line: int) -> str:
    if line < 1 or line > len(lines):
        return ""
    return " ".join(lines[line - 1].strip().split())[:180]


def _finding(
    *,
    relative: str,
    line: int,
    category: str,
    symbol: str,
    lines: list[str],
) -> Finding:
    return Finding(
        path=relative,
        line=line,
        category=category,
        symbol=symbol,
        snippet=_snippet(lines, line),
        authority_violation=_is_authority(relative),
    )


def _python_findings(path: Path, relative: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError as error:
        return [
            Finding(
                relative,
                int(error.lineno or 1),
                "unparseable_python",
                "syntax-error",
                str(error),
                _is_authority(relative),
            )
        ]

    aliases: set[str] = set()
    direct_calls: set[str] = set()
    results: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in JSON_MODULES:
                    aliases.add(alias.asname or alias.name)
                    results.append(
                        _finding(
                            relative=relative,
                            line=node.lineno,
                            category="json_import",
                            symbol=alias.name,
                            lines=lines,
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module in JSON_MODULES:
            for alias in node.names:
                direct_calls.add(alias.asname or alias.name)
            results.append(
                _finding(
                    relative=relative,
                    line=node.lineno,
                    category="json_import",
                    symbol=str(node.module),
                    lines=lines,
                )
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Attribute):
                if (
                    isinstance(function.value, ast.Name)
                    and function.value.id in aliases
                    and function.attr in JSON_CALLS
                ):
                    results.append(
                        _finding(
                            relative=relative,
                            line=node.lineno,
                            category="json_serde_call",
                            symbol=f"{function.value.id}.{function.attr}",
                            lines=lines,
                        )
                    )
                if function.attr in {"set_json_dumps", "set_json_loads"}:
                    results.append(
                        _finding(
                            relative=relative,
                            line=node.lineno,
                            category="json_adapter",
                            symbol=function.attr,
                            lines=lines,
                        )
                    )
            elif isinstance(function, ast.Name) and (
                function.id in direct_calls
                or function.id in {"Json", "Jsonb", "canonical_json"}
            ):
                results.append(
                    _finding(
                        relative=relative,
                        line=node.lineno,
                        category="json_or_compat_call",
                        symbol=function.id,
                        lines=lines,
                    )
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.casefold()
            for marker, category in STRING_MARKERS:
                if marker in lowered:
                    results.append(
                        _finding(
                            relative=relative,
                            line=getattr(node, "lineno", 1),
                            category=category,
                            symbol=marker,
                            lines=lines,
                        )
                    )
    return results


def _strip_sql_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return "\n".join(line.split("--", 1)[0] for line in source.splitlines())


def _sql_findings(path: Path, relative: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    cleaned = _strip_sql_comments(source)
    lines = source.splitlines()
    patterns = (
        (r"::\s*jsonb?\b", "sql_json_cast"),
        (r"\bjsonb?_build_[a-z_]+\s*\(", "sql_json_builder"),
        (r"\brow_to_json\s*\(", "sql_json_builder"),
        (r"\bto_jsonb?\s*\(", "sql_json_builder"),
        (r"\bjsonb?\s+(?:not\s+null|null|default|,|\))", "sql_json_column"),
    )
    results: list[Finding] = []
    for pattern, category in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.IGNORECASE):
            line = cleaned.count("\n", 0, match.start()) + 1
            results.append(
                _finding(
                    relative=relative,
                    line=line,
                    category=category,
                    symbol=match.group(0).strip(),
                    lines=lines,
                )
            )
    return results


def _text_findings(path: Path, relative: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    pattern = re.compile(
        r"\b(?:jq|json_pp)\b|\.jsonl?\b|application/json|::jsonb?\b",
        flags=re.IGNORECASE,
    )
    results: list[Finding] = []
    for line_number, line in enumerate(lines, start=1):
        for match in pattern.finditer(line):
            results.append(
                _finding(
                    relative=relative,
                    line=line_number,
                    category="text_json_tool_or_path",
                    symbol=match.group(0),
                    lines=lines,
                )
            )
    return results


def _paths(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        if path.suffix in PYTHON_SUFFIXES | SQL_SUFFIXES | TEXT_SUFFIXES:
            yield path


def scan(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in _paths(root):
        relative = path.relative_to(root).as_posix()
        if path.suffix in PYTHON_SUFFIXES:
            findings.extend(_python_findings(path, relative))
        elif path.suffix in SQL_SUFFIXES:
            findings.extend(_sql_findings(path, relative))
        else:
            findings.extend(_text_findings(path, relative))
    return sorted(set(findings))


def _render_rows(rows: list[Finding]) -> list[str]:
    output = [
        "| File | Line | Category | Symbol | Evidence |",
        "|---|---:|---|---|---|",
    ]
    for row in rows:
        evidence = row.snippet.replace("|", "\\|").replace("`", "'")
        output.append(
            f"| `{row.path}` | {row.line} | `{row.category}` | "
            f"`{row.symbol}` | `{evidence}` |"
        )
    return output


def render(findings: list[Finding]) -> str:
    violations = [row for row in findings if row.authority_violation]
    quarantine = [row for row in findings if not row.authority_violation]
    lines = [
        "# JSON Sin Bin",
        "",
        "> Generated by `scripts/audit_json_sin_bin.py`. Do not hand-edit findings.",
        "",
        "PostgreSQL execution authority, identity, replay, checkpointing, and publication",
        "must contain no JSON serialization or JSONB state. Boundary/import/export uses are",
        "listed as quarantined debt; they are visible, not endorsed.",
        "",
        "## Totals",
        "",
        f"- Authority violations: **{len(violations)}**",
        f"- Quarantined boundary/debt findings: **{len(quarantine)}**",
        f"- Total findings: **{len(findings)}**",
        "",
        "## Authority violations",
        "",
    ]
    lines.extend(_render_rows(violations) if violations else ["None."])
    lines.extend(["", "## Quarantined boundary and legacy debt", ""])
    lines.extend(_render_rows(quarantine) if quarantine else ["None."])
    lines.extend(
        [
            "",
            "## Enforcement",
            "",
            "`--check-authority` exits non-zero for any authority violation. Every other",
            "finding remains in this report until its boundary is removed or replaced.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check-authority", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    findings = scan(root)
    report = render(findings)
    if args.write is not None:
        destination = args.write
        if not destination.is_absolute():
            destination = root / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)

    violations = [row for row in findings if row.authority_violation]
    if args.check_authority and violations:
        print(
            f"JSON authority violation count: {len(violations)}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
