from __future__ import annotations

import pytest

from src.pnf.atomic_legal_registry import (
    AtomicLegalTest,
    build_atomic_registry,
    project_unresolved_atomic_residuals,
)


def _test(*, proposition_ref: str = "prop:test", gate: int = 0, positive=(), negative=()):
    return AtomicLegalTest(
        proposition_ref=proposition_ref,
        case_ref="case:test",
        legal_system_ref="TEST.LEGAL",
        source_revision_ref="source:test",
        exact_locator="s 1",
        authority_role="legislativeRuleRole",
        subject_ref="actor:test",
        gate=gate,
        positive_witness_refs=tuple(positive),
        negative_witness_refs=tuple(negative),
        evidence_fibre_ref="evidence:test",
    )


def test_zero_gate_is_unresolved_without_directional_witnesses() -> None:
    row = _test(gate=0)
    assert row.gate == 0
    assert row.to_dict()["zero_means_unresolved"] is True
    assert row.to_dict()["citation_creates_case_truth"] is False


def test_positive_gate_requires_positive_witness() -> None:
    with pytest.raises(ValueError, match="positive gate requires"):
        _test(gate=1)


def test_negative_gate_requires_failure_witness() -> None:
    with pytest.raises(ValueError, match="negative gate requires"):
        _test(gate=-1)


def test_zero_gate_rejects_directional_witness() -> None:
    with pytest.raises(ValueError, match="unresolved gate"):
        _test(gate=0, positive=("evidence:fit",))


def test_registry_rejects_contradictory_gate_for_same_case_proposition() -> None:
    zero = _test(gate=0)
    positive = _test(gate=1, positive=("evidence:fit",))
    with pytest.raises(ValueError, match="contradictory atomic gate"):
        build_atomic_registry(case_ref="case:test", tests=(zero, positive))


def test_registry_allows_distinct_exact_propositions() -> None:
    registry = build_atomic_registry(
        case_ref="case:test",
        tests=(
            _test(proposition_ref="prop:s92", gate=0),
            _test(proposition_ref="prop:s17", gate=0),
        ),
    )
    assert registry.gate_for("prop:s92") == 0
    assert registry.gate_for("prop:s17") == 0
    assert registry.to_dict()["registry_creates_authority"] is False
    assert registry.to_dict()["registry_promotes_legal_truth"] is False


def test_unresolved_case_evidence_does_not_become_legal_source_acquisition() -> None:
    registry = build_atomic_registry(case_ref="case:test", tests=(_test(gate=0),))
    residuals = project_unresolved_atomic_residuals(
        registry,
        user_side_acquisition_debt=False,
        residual_reference="reporter-held artifact",
        external_evidence_unavailable=True,
    )
    assert len(residuals) == 1
    row = residuals[0].to_dict()
    assert row["disposition"] == "blocked_external_evidence_unavailable"
    assert row["legal_source_acquisition_required"] is False
    assert row["user_side_acquisition_debt"] is False
    assert row["legal_truth_closed"] is False
