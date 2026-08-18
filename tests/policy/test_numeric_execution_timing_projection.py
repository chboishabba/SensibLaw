from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NUMERIC = ROOT / "src/policy/numeric_pnf_compilation.py"


def test_numeric_compile_projects_existing_parser_work_timing_without_new_query() -> None:
    source = NUMERIC.read_text(encoding="utf-8")
    body = source.split("def compile_numeric_pnf_document(", 1)[1].split(
        "def _record_controlled_reuse(", 1
    )[0]
    assert "parser_receipt = dict(carrier[\"parser_receipt\"])" in body
    assert "timing_details = {" in body
    assert "for key in _NUMERIC_TIMING_FIELDS" in body
    assert '"numeric_execution_timing": timing_details' in body
    assert 'message="numeric_pnf_closed"' in body
    assert "**timing_details" in body


def test_numeric_timing_fields_distinguish_work_basis_from_wall_time() -> None:
    source = NUMERIC.read_text(encoding="utf-8")
    timing = source.split("_NUMERIC_TIMING_FIELDS = (", 1)[1].split(")", 1)[0]
    for marker in (
        '"spacy_parser_work_ns"',
        '"post_parser_worker_work_ns"',
        '"post_parser_coordinator_ns"',
        '"post_parser_work_ns"',
        '"timing_basis"',
    ):
        assert marker in timing
    assert '"spacy_parser_seconds"' not in timing
    assert '"post_parser_seconds"' not in timing
