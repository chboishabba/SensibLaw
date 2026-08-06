from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PYTHON = (
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
)
AUTHORITY_SQL = tuple(
    path.relative_to(ROOT).as_posix()
    for path in sorted((ROOT / "database/postgres_migrations").glob("03[2-9]_*.sql"))
)
JSON_MODULES = {"json", "orjson", "ujson", "simplejson"}
FORBIDDEN_TEXT = (
    "::json",
    "jsonb_build_",
    "json_build_",
    ".jsonl",
    "application/json",
    "canonical-json",
)


def _python_json_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    results: list[str] = []
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in JSON_MODULES:
                    aliases.add(alias.asname or alias.name)
                    results.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in JSON_MODULES:
            results.append(str(node.module))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id in aliases:
            results.append(f"{node.func.value.id}.{node.func.attr}")
    return results


def test_python_execution_authority_contains_no_json_serde() -> None:
    failures: list[str] = []
    for relative in AUTHORITY_PYTHON:
        source = (ROOT / relative).read_text(encoding="utf-8")
        imports = _python_json_imports(source)
        if imports:
            failures.append(f"{relative}: imports/calls {imports}")
        lowered = source.casefold()
        for marker in FORBIDDEN_TEXT:
            if marker in lowered:
                failures.append(f"{relative}: contains {marker}")
    assert not failures, "\n".join(failures)


def test_new_execution_migrations_create_no_json_authority() -> None:
    failures: list[str] = []
    for relative in AUTHORITY_SQL:
        source = (ROOT / relative).read_text(encoding="utf-8")
        cleaned = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
        cleaned = "\n".join(line.split("--", 1)[0] for line in cleaned.splitlines())
        lowered = cleaned.casefold()
        for marker in ("::json", "jsonb_build_", "json_build_", "row_to_json("):
            if marker in lowered:
                failures.append(f"{relative}: contains {marker}")
        if re.search(r"\bjsonb?\s+(?:not\s+null|null|default|,|\))", cleaned, re.I):
            failures.append(f"{relative}: declares JSON/JSONB authority")
    assert not failures, "\n".join(failures)
