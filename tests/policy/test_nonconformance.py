from __future__ import annotations

from src.policy.nonconformance import build_capa_cycle, build_nonconformance


def test_nonconformance_preserves_original_residual_and_evidence() -> None:
    defect = build_nonconformance(
        nonconformance_ref="nc:1",
        subject_ref="inv:route:1",
        defect_kind="ui_ambiguity",
        requirement_refs=["req:selected-not-preferred"],
        evidence_refs=["ui:test:projection"],
        residual_refs=["residual:selected-looks-ranked"],
        root_cause_refs=["cause:render-order"],
    )
    capa = build_capa_cycle(
        capa_ref="capa:1",
        nonconformance=defect,
        define_refs=["req:selected-not-preferred"],
        measure_refs=["residual:selected-looks-ranked"],
        analyse_refs=["cause:render-order"],
        improve_refs=["impl:stable-id-order"],
        control_refs=["test:render-order-no-ranking"],
    )
    assert capa["original_residual_refs"] == ["residual:selected-looks-ranked"]
    assert capa["original_evidence_refs"] == ["ui:test:projection"]
    assert capa["creates_semantic_authority"] is False


def test_nonconformance_defect_taxonomy_contains_governance_failures() -> None:
    expected = {
        "semantic_mismatch",
        "provenance_loss",
        "authority_leak",
        "scope_leak",
        "privacy_exposure",
        "security_boundary_violation",
        "ui_ambiguity",
        "replay_nondeterminism",
        "performance_regression",
        "hidden_work_amplification",
    }
    from src.policy.nonconformance import DEFECT_KINDS
    assert expected <= set(DEFECT_KINDS)
