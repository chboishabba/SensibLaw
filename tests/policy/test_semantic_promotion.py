from __future__ import annotations

from src.policy.semantic_promotion import (
    ABSTAINED,
    CONTESTED_CANDIDATE_SCHEMA_VERSION,
    CANDIDATE_CONFLICT,
    HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION,
    MANDATORY_CONTESTED_CANDIDATE_FIELDS,
    MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS,
    MANDATORY_RELATION_CANDIDATE_FIELDS,
    NON_TRUTH_BEARING_FIELDS,
    PROMOTED_FALSE,
    PROMOTED_TRUE,
    RELATION_CANDIDATE_SCHEMA_VERSION,
    TRUTH_BEARING_FIELDS,
    build_contested_claim_candidate,
    build_hotspot_pack_candidate,
    build_relation_candidate,
    promote_contested_claim,
    promote_hotspot_pack_candidate,
    promote_relation_candidate,
    validate_contested_claim_candidate,
    validate_hotspot_pack_candidate,
    validate_relation_candidate,
)


def test_promote_contested_claim_abstains_for_non_structural_basis() -> None:
    result = promote_contested_claim(
        build_contested_claim_candidate(
            basis="heuristic",
            claim_span={"text": "A", "start": 0, "end": 1},
            response_span={"text": "B", "start": 0, "end": 1},
            speech_act="admit",
            polarity="positive",
            target_component="predicate_text",
            support_direction="for",
            conflict_state="undisputed",
            evidentiary_state="supported",
        )
    )
    assert result["status"] == ABSTAINED
    assert result["reason"] == "non_structural_basis"


def test_promote_contested_claim_promotes_true_for_structural_support() -> None:
    result = promote_contested_claim(
        build_contested_claim_candidate(
            basis="structural",
            claim_span={"text": "A", "start": 0, "end": 1},
            response_span={"text": "B", "start": 0, "end": 1},
            speech_act="admit",
            polarity="positive",
            target_component="predicate_text",
            support_direction="for",
            conflict_state="undisputed",
            evidentiary_state="supported",
        )
    )
    assert result["status"] == PROMOTED_TRUE


def test_promote_contested_claim_promotes_false_for_structural_dispute() -> None:
    result = promote_contested_claim(
        build_contested_claim_candidate(
            basis="structural",
            claim_span={"text": "A", "start": 0, "end": 1},
            response_span={"text": "B", "start": 0, "end": 1},
            speech_act="deny",
            polarity="negative",
            target_component="predicate_text",
            support_direction="against",
            conflict_state="disputed",
            evidentiary_state="unproven",
        )
    )
    assert result["status"] == PROMOTED_FALSE


def test_promote_contested_claim_marks_conflict_for_mixed_state() -> None:
    result = promote_contested_claim(
        build_contested_claim_candidate(
            basis="structural",
            claim_span={"text": "A", "start": 0, "end": 1},
            response_span={"text": "B", "start": 0, "end": 1},
            speech_act="other",
            polarity="qualified",
            target_component="predicate_text",
            support_direction="mixed",
            conflict_state="partially_reconciled",
            evidentiary_state="weakly_supported",
        )
    )
    assert result["status"] == CANDIDATE_CONFLICT


def test_build_contested_claim_candidate_emits_minimal_schema() -> None:
    candidate = build_contested_claim_candidate(
        basis="structural",
        claim_span={"text": "A", "start": 0, "end": 1},
        response_span={"text": "B", "start": 0, "end": 1},
        speech_act="deny",
        polarity="negative",
        target_component="predicate_text",
        support_direction="against",
        conflict_state="disputed",
        evidentiary_state="unproven",
    )
    assert candidate["schema_version"] == CONTESTED_CANDIDATE_SCHEMA_VERSION
    assert candidate["candidate_kind"] == "contested_claim"
    for field in MANDATORY_CONTESTED_CANDIDATE_FIELDS:
        assert field in candidate


def test_validate_contested_claim_candidate_rejects_missing_required_field() -> None:
    try:
        validate_contested_claim_candidate({"basis": "structural"})
    except ValueError as exc:
        assert "Missing contested semantic candidate fields" in str(exc)
    else:
        raise AssertionError("Expected validate_contested_claim_candidate to fail")


def test_truth_bearing_field_inventory_is_explicit() -> None:
    assert "promotion_status" in TRUTH_BEARING_FIELDS
    assert "support_direction" in TRUTH_BEARING_FIELDS
    assert "coverage_status" not in TRUTH_BEARING_FIELDS
    assert "coverage_status" in NON_TRUTH_BEARING_FIELDS


def test_build_relation_candidate_emits_minimal_schema() -> None:
    candidate = build_relation_candidate(
        basis="structural",
        event_id="ev1",
        predicate_key="signed",
        subject={"canonical_key": "actor:a"},
        object={"canonical_key": "legal_ref:b"},
        lane_promotion_status="promoted",
        confidence_tier="medium",
    )
    assert candidate["schema_version"] == RELATION_CANDIDATE_SCHEMA_VERSION
    assert candidate["candidate_kind"] == "semantic_relation"
    for field in MANDATORY_RELATION_CANDIDATE_FIELDS:
        assert field in candidate


def test_validate_relation_candidate_rejects_missing_required_field() -> None:
    try:
        validate_relation_candidate({"basis": "structural"})
    except ValueError as exc:
        assert "Missing relation semantic candidate fields" in str(exc)
    else:
        raise AssertionError("Expected validate_relation_candidate to fail")


def test_promote_relation_candidate_promotes_true_for_structural_promoted_relation() -> None:
    result = promote_relation_candidate(
        build_relation_candidate(
            basis="structural",
            event_id="ev1",
            predicate_key="signed",
            subject={"canonical_key": "actor:a"},
            object={"canonical_key": "legal_ref:b"},
            lane_promotion_status="promoted",
            confidence_tier="medium",
        )
    )
    assert result["status"] == PROMOTED_TRUE


def test_promote_relation_candidate_abstains_for_non_promoted_or_non_structural_relation() -> None:
    candidate_result = promote_relation_candidate(
        build_relation_candidate(
            basis="structural",
            event_id="ev1",
            predicate_key="signed",
            subject={"canonical_key": "actor:a"},
            object={"canonical_key": "legal_ref:b"},
            lane_promotion_status="candidate",
            confidence_tier="low",
        )
    )
    assert candidate_result["status"] == ABSTAINED

    heuristic_result = promote_relation_candidate(
        build_relation_candidate(
            basis="heuristic",
            event_id="ev1",
            predicate_key="signed",
            subject={"canonical_key": "actor:a"},
            object={"canonical_key": "legal_ref:b"},
            lane_promotion_status="promoted",
            confidence_tier="medium",
        )
    )
    assert heuristic_result["status"] == ABSTAINED


def test_build_hotspot_pack_candidate_emits_minimal_schema() -> None:
    candidate = build_hotspot_pack_candidate(
        basis="structural",
        pack_id="pack1",
        hotspot_family="mixed_order",
        lane_promotion_status="promoted",
        status="report_backed",
        cluster_count=3,
    )
    assert candidate["schema_version"] == HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION
    assert candidate["candidate_kind"] == "hotspot_pack"
    for field in MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS:
        assert field in candidate


def test_validate_hotspot_pack_candidate_rejects_missing_required_field() -> None:
    try:
        validate_hotspot_pack_candidate({"basis": "structural"})
    except ValueError as exc:
        assert "Missing hotspot pack semantic candidate fields" in str(exc)
    else:
        raise AssertionError("Expected validate_hotspot_pack_candidate to fail")


def test_promote_hotspot_pack_candidate_maps_promoted_and_promotable_states() -> None:
    promoted = promote_hotspot_pack_candidate(
        build_hotspot_pack_candidate(
            basis="structural",
            pack_id="pack1",
            hotspot_family="mixed_order",
            lane_promotion_status="promoted",
            status="report_backed",
            cluster_count=3,
        )
    )
    assert promoted["status"] == PROMOTED_TRUE

    promotable = promote_hotspot_pack_candidate(
        build_hotspot_pack_candidate(
            basis="structural",
            pack_id="pack2",
            hotspot_family="entity_kind_collapse",
            lane_promotion_status="promotable",
            status="fixture_backed",
            cluster_count=2,
        )
    )
    assert promotable["status"] == ABSTAINED
