from __future__ import annotations

from src.policy.evidence_surface_identity import build_evidence_surface_identity


def test_mapping_key_order_does_not_change_content_identity() -> None:
    left = {"subject_qid": "Q1", "coverage": {"P31": "observed", "P279": "incomplete"}}
    right = {"coverage": {"P279": "incomplete", "P31": "observed"}, "subject_qid": "Q1"}
    assert build_evidence_surface_identity(left)["content_id"] == build_evidence_surface_identity(right)["content_id"]


def test_semantic_content_change_changes_content_identity() -> None:
    left = {"subject_qid": "Q1", "coverage": {"P31": "observed"}}
    right = {"subject_qid": "Q1", "coverage": {"P31": "uninspected"}}
    assert build_evidence_surface_identity(left)["content_id"] != build_evidence_surface_identity(right)["content_id"]


def test_content_identity_has_no_semantic_authority() -> None:
    identity = build_evidence_surface_identity({"subject_qid": "Q1"})
    assert identity["identity_scope"] == "rendered_content_only"
    assert identity["truth_authority"] is False
    assert identity["identity_alignment_authority"] is False
    assert identity["promotion_authority"] is False
    assert identity["edit_authority"] is False
