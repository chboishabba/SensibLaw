from __future__ import annotations

import fnmatch
import subprocess
import time
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from tree_sitter import Query, QueryCursor

from .languages import language_for_path, parser_for_language, parser_name
from .pnf import pnf_candidate


SCHEMA = "code_observation_v1"
CALL_NODE_TYPES = {"call", "call_expression"}
ASSERTION_NODE_TYPES = {"assert_statement", "assertion"}
READ_CALLEES = {"open", "readfile", "readfilesync"}
WRITE_CALLEES = {"writefile", "writefilesync"}


def observe_paths(
    root: Path,
    *,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    projection_boundary: list[str] | None = None,
    bounded_absence_target: str | None = None,
) -> list[dict[str, Any]]:
    root = root.resolve()
    include_globs = include_globs or ["**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"]
    exclude_globs = exclude_globs or ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"]
    files = _scan_files(root, include_globs, exclude_globs)
    commit = _git_commit(root)
    repo = root.name
    scope = {
        "scope_id": f"repo:{repo}:code-observer",
        "root": str(root),
        "include_globs": include_globs,
        "exclude_globs": exclude_globs,
        "files_scanned": len(files),
    }
    rows: list[dict[str, Any]] = []
    observed_call_count = 0
    for path in files:
        language = language_for_path(path)
        if language is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        parser = parser_for_language(language)
        tree = parser.parse(text.encode("utf-8"))
        file_scope = {**scope, "parser": parser_name(language)}
        file_rows = _extract_rows(
            root,
            path,
            text,
            tree.root_node,
            language=language,
            repo=repo,
            commit=commit,
            scan_scope=file_scope,
            projection_boundary=projection_boundary or [],
        )
        if bounded_absence_target:
            observed_call_count += sum(1 for row in file_rows if row.get("callee") == bounded_absence_target)
        rows.extend(file_rows)
    if bounded_absence_target and observed_call_count == 0:
        rows.append(
            {
                "schema": SCHEMA,
                "ts": _utc_now(),
                "repo": repo,
                "commit": commit,
                "path": str(root),
                "language": "mixed",
                "observation_kind": "bounded_absence_scan",
                "symbol": bounded_absence_target,
                "callee": None,
                "module": None,
                "line_start": 0,
                "line_end": 0,
                "byte_range": [0, 0],
                "scan_scope": {**scope, "observed_call_count": 0, "target_pattern": bounded_absence_target},
                "pnf_candidates": [],
                "provenance": [
                    {
                        "kind": "bounded_scan_receipt",
                        "scope_id": scope["scope_id"],
                        "root": str(root),
                        "include_globs": include_globs,
                        "files_scanned": len(files),
                        "commit": commit,
                    }
                ],
                "non_authoritative": True,
            }
        )
    return rows


def _scan_files(root: Path, include_globs: list[str], exclude_globs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if not any(_glob_match(rel, pattern) for pattern in include_globs):
            continue
        if any(_glob_match(rel, pattern) for pattern in exclude_globs):
            continue
        if language_for_path(path):
            paths.append(path)
    return sorted(paths)


def _glob_match(rel: str, pattern: str) -> bool:
    if fnmatch.fnmatch(rel, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatch(rel, pattern[3:]):
        return True
    return False


def _extract_rows(
    root: Path,
    path: Path,
    text: str,
    node: Any,
    *,
    language: str,
    repo: str,
    commit: str,
    scan_scope: dict[str, Any],
    projection_boundary: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rel = path.relative_to(root).as_posix()
    for captures in _query_matches(language, node):
        declaration = _first_capture(captures, "symbol.declaration")
        if declaration is not None:
            for name in _captured_names(captures, text) or _declaration_names(declaration, text):
                _append_unique(
                    rows,
                    _row(repo, commit, rel, language, "symbol_declared", declaration, text, scan_scope, symbol=name),
                )

        observed_import = _first_capture(captures, "import.observed")
        if observed_import is not None:
            module = _compact_text(observed_import, text)
            _append_unique(
                rows,
                _row(repo, commit, rel, language, "import_observed", observed_import, text, scan_scope, module=module),
            )

        observed_call = _first_capture(captures, "call.observed")
        if observed_call is not None:
            callee_node = _first_capture(captures, "call.callee")
            callee = _compact_text(callee_node, text) if callee_node is not None else _call_name(observed_call, text)
            if callee:
                obs = "call_observed"
                if _is_file_read_callee(callee):
                    obs = "file_read_observed"
                if _is_file_write_callee(callee):
                    obs = "file_write_observed"
                _append_unique(rows, _row(repo, commit, rel, language, obs, observed_call, text, scan_scope, callee=callee))
                if callee.endswith("add_argument"):
                    flag = _first_string_child(observed_call, text)
                    if flag and flag.startswith("--"):
                        _append_unique(
                            rows,
                            _row(
                                repo,
                                commit,
                                rel,
                                language,
                                "cli_flag_observed",
                                observed_call,
                                text,
                                scan_scope,
                                symbol=flag,
                            ),
                        )

        assertion = _first_capture(captures, "test.assertion")
        if assertion is not None and (
            assertion.type in ASSERTION_NODE_TYPES or _is_test_assertion_call(assertion, text)
        ):
            _append_unique(
                rows,
                _row(
                    repo,
                    commit,
                    rel,
                    language,
                    "test_assertion_observed",
                    assertion,
                    text,
                    scan_scope,
                    symbol=_compact_text(assertion, text)[:120],
                ),
            )

        schema_node = _first_capture(captures, "schema.field") or _first_capture(captures, "schema.literal")
        if schema_node is not None:
            value = _schema_field_name(schema_node, text)
            if value:
                _append_unique(
                    rows,
                    _row(repo, commit, rel, language, "schema_field_observed", schema_node, text, scan_scope, symbol=value),
                )

    for current in _walk(node):
        snippet = _compact_text(current, text)
        if projection_boundary and any(pattern in snippet for pattern in projection_boundary):
            _append_unique(
                rows,
                _row(
                    repo,
                    commit,
                    rel,
                    language,
                    "projection_boundary_observed",
                    current,
                    text,
                    scan_scope,
                    symbol=snippet[:120],
                ),
            )
    return rows


def _row(
    repo: str,
    commit: str,
    rel: str,
    language: str,
    observation_kind: str,
    node: Any,
    text: str,
    scan_scope: dict[str, Any],
    *,
    symbol: str | None = None,
    callee: str | None = None,
    module: str | None = None,
) -> dict[str, Any]:
    line_start = int(node.start_point[0]) + 1
    line_end = int(node.end_point[0]) + 1
    byte_range = [int(node.start_byte), int(node.end_byte)]
    provenance = f"repo:{repo}@{commit}:{rel}:{line_start}"
    predicate = {
        "symbol_declared": "code_declares_symbol",
        "import_observed": "code_imports_module",
        "call_observed": "code_calls_symbol",
        "cli_flag_observed": "code_defines_cli_flag",
        "file_read_observed": "code_reads_file",
        "file_write_observed": "code_writes_file",
        "test_assertion_observed": "code_test_asserts_behavior",
        "schema_field_observed": "code_schema_field_observed",
        "projection_boundary_observed": "code_projection_boundary",
    }.get(observation_kind)
    value = symbol or callee or module or _compact_text(node, text)[:120]
    rows = []
    if predicate:
        role_name = "callee" if callee else "module" if module else "symbol"
        rows.append(
            pnf_candidate(
                predicate,
                f"{language}.{observation_kind}:{value}",
                {"file": (rel, "file_path"), role_name: (value, "symbol"), "line": (str(line_start), "line_number")},
                provenance,
            )
        )
    return {
        "schema": SCHEMA,
        "ts": _utc_now(),
        "repo": repo,
        "commit": commit,
        "path": rel,
        "language": language,
        "observation_kind": observation_kind,
        "symbol": symbol,
        "callee": callee,
        "module": module,
        "line_start": line_start,
        "line_end": line_end,
        "byte_range": byte_range,
        "scan_scope": scan_scope,
        "pnf_candidates": rows,
        "provenance": [{"kind": "source_span", "path": rel, "line_start": line_start, "line_end": line_end, "byte_range": byte_range, "commit": commit}],
        "non_authoritative": True,
    }


def _walk(node: Any) -> Iterable[Any]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _query_matches(language: str, node: Any) -> Iterable[dict[str, list[Any]]]:
    query_path = files("src.code_observer").joinpath("queries", f"{language}.scm")
    query = Query(parser_for_language(language).language, query_path.read_text(encoding="utf-8"))
    cursor = QueryCursor(query)
    for _, captures in cursor.matches(node):
        yield captures


def _first_capture(captures: dict[str, list[Any]], name: str) -> Any | None:
    nodes = captures.get(name) or []
    return nodes[0] if nodes else None


def _captured_names(captures: dict[str, list[Any]], text: str) -> list[str]:
    return [_compact_text(node, text) for node in captures.get("symbol.name", []) if _compact_text(node, text)]


def _append_unique(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
    key = (
        row["observation_kind"],
        row["path"],
        tuple(row["byte_range"]),
        row.get("symbol"),
        row.get("callee"),
        row.get("module"),
    )
    for existing in rows:
        existing_key = (
            existing["observation_kind"],
            existing["path"],
            tuple(existing["byte_range"]),
            existing.get("symbol"),
            existing.get("callee"),
            existing.get("module"),
        )
        if existing_key == key:
            return
    rows.append(row)


def _node_name(node: Any) -> str | None:
    child = node.child_by_field_name("name")
    if child is not None and child.text:
        return child.text.decode("utf-8", errors="replace")
    for child in node.named_children:
        if child.type in {"identifier", "property_identifier", "type_identifier"} and child.text:
            return child.text.decode("utf-8", errors="replace")
    return None


def _declaration_names(node: Any, text: str) -> list[str]:
    if node.type in {"lexical_declaration", "variable_declaration"}:
        names: list[str] = []
        for child in node.named_children:
            if child.type != "variable_declarator":
                continue
            value = child.child_by_field_name("value")
            if value is None or value.type not in {
                "arrow_function",
                "function_expression",
                "function_declaration",
                "class",
                "class_declaration",
            }:
                continue
            name = child.child_by_field_name("name")
            if name is not None:
                names.append(_compact_text(name, text))
        return [name for name in names if name]
    name = _node_name(node)
    return [name] if name else []


def _call_name(node: Any, text: str) -> str | None:
    fn = node.child_by_field_name("function") or (node.named_children[0] if node.named_children else None)
    if fn is None:
        return None
    return _compact_text(fn, text)


def _is_file_read_callee(callee: str) -> bool:
    normalized = callee.lower()
    return normalized in READ_CALLEES or normalized.endswith((".open", ".read_text", ".read", ".readfile", ".readfilesync"))


def _is_file_write_callee(callee: str) -> bool:
    normalized = callee.lower()
    return normalized in WRITE_CALLEES or normalized.endswith((".write_text", ".write", ".writefile", ".writefilesync"))


def _is_test_assertion_call(node: Any, text: str) -> bool:
    if node.type not in CALL_NODE_TYPES:
        return False
    callee = _call_name(node, text)
    if not callee:
        return False
    return callee in {"expect", "assert"} or callee.startswith("assert.") or ".to" in callee


def _schema_field_name(node: Any, text: str) -> str | None:
    value = _compact_text(node, text).strip("\"'`")
    if value in {"schema", "schema_version"}:
        return value
    key = node.child_by_field_name("key")
    if key is not None:
        key_text = _compact_text(key, text).strip("\"'`")
        if key_text in {"schema", "schema_version"}:
            return key_text
    return None


def _first_string_child(node: Any, text: str) -> str | None:
    for child in _walk(node):
        if child.type in {"string", "string_fragment"}:
            return _compact_text(child, text).strip("\"'`")
    return None


def _compact_text(node: Any, text: str) -> str:
    return text[int(node.start_byte): int(node.end_byte)].replace("\n", " ").strip()


def _git_commit(root: Path) -> str:
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], check=True, text=True, capture_output=True)
        return proc.stdout.strip()
    except Exception:
        return "unknown"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
