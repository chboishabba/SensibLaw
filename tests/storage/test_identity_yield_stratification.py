from pathlib import Path


REPORTER = Path("scripts/report_identity_evidence_yield.py")


def test_report_separates_proofs_from_factor_derivations() -> None:
    source = REPORTER.read_text(encoding="utf-8")
    assert "Admitted parser source proofs" in source
    assert "Parser anchor/base witnesses" in source
    assert "Admitted typed-demand source proofs" in source
    assert "Factor-bearing identity projections" in source
    assert "Level-3 identity substitutions" in source
    assert "A parser source proof is not automatically a factor derivation" in source


def test_report_surfaces_bounded_name_overflow() -> None:
    source = REPORTER.read_text(encoding="utf-8")
    assert "semantic_pnf_proper_name_evidence_overflow" in source
    assert "Proper-name overflow mentions" in source
    assert "Unretained ambiguous name targets" in source


def test_default_run_must_have_registered_identity() -> None:
    source = REPORTER.read_text(encoding="utf-8")
    assert "JOIN execution.semantic_pnf_run_identity AS identity" in source
    assert "no numeric PNF run with a registered run identity is available" in source
