from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_python")
pytest.importorskip("tree_sitter_javascript")
pytest.importorskip("tree_sitter_typescript")

from src.code_observer import observe_paths


def test_tree_sitter_observer_emits_evidence_only_code_rows(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "example.py").write_text(
        "from pathlib import Path\n\n"
        "def main():\n"
        "    parser.add_argument('--dry-run')\n"
        "    Path('x').read_text()\n"
        "    assert True\n",
        encoding="utf-8",
    )

    rows = observe_paths(
        src,
        include_globs=["**/*.py"],
        bounded_absence_target="subprocess.Popen",
        projection_boundary=["Path("],
    )

    kinds = {row["observation_kind"] for row in rows}
    assert {
        "symbol_declared",
        "import_observed",
        "call_observed",
        "cli_flag_observed",
        "file_read_observed",
        "test_assertion_observed",
        "projection_boundary_observed",
    } <= kinds
    _assert_contract_rows(rows)
    absence = [row for row in rows if row["observation_kind"] == "bounded_absence_scan"][0]
    assert absence["pnf_candidates"] == []
    assert absence["scan_scope"]["observed_call_count"] == 0


def test_tree_sitter_observer_covers_javascript_typescript_and_tsx(tmp_path: Path) -> None:
    (tmp_path / "example.js").write_text(
        "import fs from 'fs';\n"
        "function run(){ fs.readFileSync('x'); expect(value).toEqual(1); }\n",
        encoding="utf-8",
    )
    (tmp_path / "example.ts").write_text(
        "import { join } from 'path';\n"
        "const build = (name: string) => join('x', name);\n",
        encoding="utf-8",
    )
    (tmp_path / "example.tsx").write_text(
        "import React from 'react';\n"
        "export function Widget(){ return <div>{React.createElement('span')}</div>; }\n",
        encoding="utf-8",
    )

    rows = observe_paths(tmp_path, include_globs=["**/*.js", "**/*.ts", "**/*.tsx"])
    _assert_contract_rows(rows)

    by_path = {}
    for row in rows:
        by_path.setdefault(row["path"], set()).add(row["observation_kind"])
    assert {"symbol_declared", "import_observed", "file_read_observed", "test_assertion_observed"} <= by_path["example.js"]
    assert {"symbol_declared", "import_observed", "call_observed"} <= by_path["example.ts"]
    assert {"symbol_declared", "import_observed", "call_observed"} <= by_path["example.tsx"]


def test_tree_sitter_observer_jsonl_serializable(tmp_path: Path) -> None:
    (tmp_path / "example.py").write_text("def f():\n    return {'schema': 'x'}\n", encoding="utf-8")
    rows = observe_paths(tmp_path, include_globs=["**/*.py"])
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    assert "code_observation_v1" in text


def _assert_contract_rows(rows: list[dict[str, object]]) -> None:
    assert rows
    allowed_kinds = {
        "symbol_declared",
        "import_observed",
        "call_observed",
        "cli_flag_observed",
        "file_read_observed",
        "file_write_observed",
        "test_assertion_observed",
        "schema_field_observed",
        "projection_boundary_observed",
        "bounded_absence_scan",
    }
    for row in rows:
        assert row["schema"] == "code_observation_v1"
        assert row["observation_kind"] in allowed_kinds
        assert row["non_authoritative"] is True
        assert row["provenance"]
        assert row["scan_scope"]
        assert "task_id" not in row
        assert "kanban" not in row
        if row["observation_kind"] != "bounded_absence_scan":
            assert row["line_start"] >= 1
            assert row["line_end"] >= row["line_start"]
        byte_start, byte_end = row["byte_range"]
        assert byte_start <= byte_end
        for candidate in row["pnf_candidates"]:
            assert candidate["source_observation_schema"] == "code_observation_v1"
            assert candidate["domain"] == "code_structure"
            assert candidate["wrapper"]["evidence_only"] is True
            assert candidate["qualifiers"]["polarity"] == "positive"
            assert candidate["provenance"]
            assert "task_id" not in candidate
            assert "kanban" not in candidate
