#!/usr/bin/env python3
"""Fail closed on serialization or textual PNF execution authority."""

from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PYTHON_AUTHORITY = (
    Path("src/pnf/numeric_hyperfabric.py"),
    Path("src/pnf/numeric_operator_composition.py"),
    Path("src/policy/numeric_pnf_compilation.py"),
    Path("src/policy/streaming_spacy_parser_execution.py"),
    Path("src/storage/postgres/numeric_symbol_store.py"),
    Path("src/storage/postgres/numeric_hierarchy_planner.py"),
    Path("src/storage/postgres/numeric_hyperfabric_store.py"),
    Path("src/storage/postgres/spacy_numeric_projection.py"),
    Path("src/storage/postgres/streaming_spacy_execution.py"),
)
SQL_AUTHORITY = tuple(
    path
    for ordinal in range(40, 49)
    for path in sorted(
        (ROOT / "database/postgres_migrations").glob(f"{ordinal:03d}_*.sql")
    )
)
FORBIDDEN_TEXT = (
    "::json",
    "jsonb_build",
    "json_build",
    "row_to_json",
    "to_json",
    ".jsonl",
    "application/json",
    "canonical-json",
)
JSON_MODULES = {"json", "orjson", "ujson", "simplejson"}


def _python_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in JSON_MODULES:
                    violations.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module in JSON_MODULES:
            violations.append(f"{path}:{node.lineno}: from {node.module}")
        elif isinstance(node, ast.Name) and node.id in {
            "canonical_json",
            "Json",
            "Jsonb",
        }:
            violations.append(f"{path}:{node.lineno}: {node.id}")
    lowered = source.casefold()
    for marker in FORBIDDEN_TEXT:
        if marker in lowered:
            violations.append(f"{path}: forbidden marker {marker}")
    return violations


def _sql_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line.split("--", 1)[0] for line in source.splitlines()
    ).casefold()
    violations: list[str] = []
    for marker in FORBIDDEN_TEXT:
        if marker in without_comments:
            violations.append(f"{path}: forbidden marker {marker}")
    if re.search(r"\bjsonb?\b", without_comments):
        violations.append(f"{path}: JSON/JSONB SQL type")
    return violations


def main() -> int:
    violations: list[str] = []
    for relative in PYTHON_AUTHORITY:
        path = ROOT / relative
        if not path.is_file():
            violations.append(f"missing numeric authority file: {relative}")
        else:
            violations.extend(_python_violations(path))
    if len(SQL_AUTHORITY) != 9:
        violations.append(
            "expected exactly migrations 040..048 for numeric authority; "
            f"found {len(SQL_AUTHORITY)}"
        )
    for path in SQL_AUTHORITY:
        if not path.is_file():
            violations.append(f"missing numeric authority migration: {path}")
        else:
            violations.extend(_sql_violations(path))

    migration_source = "\n".join(
        path.read_text(encoding="utf-8") for path in SQL_AUTHORITY
    )
    required = (
        "symbol_id BIGINT",
        "kind_id SMALLINT",
        "token_id BIGINT",
        "sentence_id BIGINT",
        "semantic_pnf_hyperedge",
        "semantic_pnf_interface_ancestor",
        "distance_power SMALLINT",
        "semantic_pnf_interface_typed_ancestor",
        "semantic_pnf_visible_lookup",
        "semantic_pnf_mdl_profile",
        "admit_numeric_pnf_interface_export",
        "derive_numeric_sentence_mentions",
        "derive_numeric_region_recurrence",
        "semantic_pnf_demand_candidate",
        "plan_numeric_pnf_demand_candidates",
        "semantic_pnf_visible_demand_planning",
    )
    for marker in required:
        if marker not in migration_source:
            violations.append(f"numeric PNF schema lacks {marker}")

    numeric_source = (ROOT / PYTHON_AUTHORITY[0]).read_text(encoding="utf-8")
    if (
        "raise TypeError" not in numeric_source
        or "numeric graph identity" not in numeric_source
    ):
        violations.append("numeric identity does not fail closed on text")
    if "O(N * W * B)" not in numeric_source:
        violations.append("bounded segmentation complexity contract is absent")
    if "_prefix_join" in numeric_source:
        violations.append("bounded segmentation still rescans interval prefixes")

    planner_source = (
        ROOT / "src/storage/postgres/numeric_hierarchy_planner.py"
    ).read_text(encoding="utf-8")
    for marker in (
        "InterfaceSketch",
        "plan_interface_segments",
        "object_keys=self.object_keys | other.object_keys",
        "O(N * W * B)",
        "_refresh_reductive_measure",
    ):
        if marker not in planner_source:
            violations.append(f"reductive hierarchy planner lacks {marker}")

    strict_source = (
        ROOT / "src/policy/streaming_spacy_parser_execution.py"
    ).read_text(encoding="utf-8")
    if "persist_numeric_pnf_document" not in strict_source:
        violations.append("strict persistence does not use numeric PNF authority")
    strict_branch = strict_source.split("def persist_wrapper", 1)[-1]
    if "return original_persist(*bound.args, **bound.kwargs)" not in strict_branch:
        violations.append("compatibility persistence fallback is missing")
    if strict_branch.count("persist_numeric_pnf_document(") != 1:
        violations.append("strict numeric persistence is not singular")

    if violations:
        print("Numeric hyperfabric authority violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("numeric hyperfabric authority: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
