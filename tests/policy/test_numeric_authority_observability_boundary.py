from __future__ import annotations

from pathlib import Path

from src.policy import numeric_pnf_compilation as numeric


ROOT = Path(__file__).resolve().parents[2]
NUMERIC = ROOT / "src/policy/numeric_pnf_compilation.py"


def test_document_cardinality_scans_are_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_AUTHORITY_COUNTS", raising=False)
    assert not numeric._numeric_authority_counts_enabled()


def test_document_cardinality_scans_can_be_enabled_for_diagnostics(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_NUMERIC_AUTHORITY_COUNTS", "1")
    assert numeric._numeric_authority_counts_enabled()


def test_authority_function_separates_required_refs_from_diagnostic_counts() -> None:
    source = NUMERIC.read_text(encoding="utf-8")
    body = source.split("def _authority_refs(", 1)[1].split(
        "def compile_numeric_pnf_document(", 1
    )[0]
    assert '"document_interface_id": document_interface_id' in body
    assert '"interface_cardinality": interface_cardinality' in body
    assert '"demand_count": len(demand_refs)' in body
    assert "if _numeric_authority_counts_enabled():" in body
    assert "semantic_parser_token" in body
    assert '"diagnostic_counts_measured": True' in body
