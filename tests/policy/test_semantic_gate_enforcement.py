from __future__ import annotations

import inspect

from scripts import build_affidavit_coverage_review as contested_module
from src.gwb_us_law import semantic as gwb_module
from src.ontology import wikidata_hotspot as hotspot_module
from src.transcript_semantic import semantic as transcript_module


def test_contested_lane_truth_bearing_fields_flow_through_claim_state_and_central_gate() -> None:
    src = inspect.getsource(contested_module)

    assert "promote_contested_claim(" in src
    assert '"promotion_status": promotion["status"]' in src
    assert '"support_direction": claim_state["support_direction"]' in src
    assert '"conflict_state": claim_state["conflict_state"]' in src
    assert '"evidentiary_state": claim_state["evidentiary_state"]' in src
    assert '"operational_status": claim_state["operational_status"]' in src


def test_relation_lanes_use_central_gate_for_canonical_truth_fields() -> None:
    for module in (gwb_module, transcript_module):
        src = inspect.getsource(module)
        assert "promote_relation_candidate(" in src
        assert '"canonical_promotion_status": promotion["status"]' in src
        assert '"canonical_promotion_basis": promotion["basis"]' in src
        assert '"canonical_promotion_reason": promotion["reason"]' in src


def test_hotspot_lane_uses_central_gate_for_canonical_truth_fields() -> None:
    src = inspect.getsource(hotspot_module)

    assert "promote_hotspot_pack_candidate(" in src
    assert '"canonical_promotion_status": promotion["status"]' in src
    assert '"canonical_promotion_basis": promotion["basis"]' in src
    assert '"canonical_promotion_reason": promotion["reason"]' in src


def test_mission_observer_lane_remains_outside_truth_bearing_promotion_family() -> None:
    src = inspect.getsource(transcript_module._build_transcript_mission_observer)

    assert '"canonical_promotion_status"' not in src
    assert '"support_direction"' not in src
    assert '"conflict_state"' not in src
    assert '"evidentiary_state"' not in src
