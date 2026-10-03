from __future__ import annotations

import pytest

from src.policy.control_case import (
    EVIDENCE_STATES,
    GOV1_PROFILE_ID,
    SERVICE_CHANGE_STATES,
    build_control_case,
)
from src.policy.control_profiles import get_control_profile


def test_gov1_profile_has_portable_control_families_without_certification_claim() -> None:
    profile = get_control_profile(GOV1_PROFILE_ID)
    family_ids = {row["control_group_id"] for row in profile["control_groups"]}
    assert {
        "authority_provenance",
        "requirements_acceptance",
        "ai_lifecycle",
        "ai_risk",
        "information_security",
        "privacy_information_management",
        "access_scope",
        "human_oversight",
        "uncertainty_non_promotion",
        "service_change_release_incident",
        "capa_defect_reduction",
        "usability_hcd_accessibility",
        "architecture_traceability",
    } <= family_ids
    assert profile["source_standards"]
    assert "certified" not in profile
    assert "compliant" not in profile


def test_control_case_keeps_service_and_evidence_states_orthogonal() -> None:
    case = build_control_case(
        control_case_ref="govcase:inv1",
        subject_ref="inv:obligation:1",
        subject_kind="inv_acquisition",
        requirement_refs=["req:pi:no-authority-promotion"],
        risk_refs=["risk:ui-priority-collapse"],
        control_refs=["control:frontier-no-ranking"],
        implementation_refs=["slr:investigation_acquisition"],
        evidence_refs=["test:slr:pareto"],
        residual_refs=["residual:runtime-pg-fixture"],
        service_change_state="implemented",
        evidence_state="compile_checked",
    )
    assert case["service_change_state"] == "implemented"
    assert case["evidence_state"] == "compile_checked"
    assert case["certification_claim"] is False
    assert case["creates_semantic_authority"] is False
    assert case["service_change_state"] in SERVICE_CHANGE_STATES
    assert case["evidence_state"] in EVIDENCE_STATES


def test_control_case_rejects_empty_control_or_evidence_identity() -> None:
    kwargs = dict(
        control_case_ref="govcase:1",
        subject_ref="subject:1",
        subject_kind="inv_acquisition",
        requirement_refs=["req:1"],
        risk_refs=["risk:1"],
        control_refs=["control:1"],
        implementation_refs=["impl:1"],
        evidence_refs=["evidence:1"],
        residual_refs=[],
        service_change_state="implemented",
        evidence_state="source_written",
    )
    with pytest.raises(ValueError):
        build_control_case(**{**kwargs, "control_refs": []})
    with pytest.raises(ValueError):
        build_control_case(**{**kwargs, "evidence_refs": []})
