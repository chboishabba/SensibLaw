from __future__ import annotations

import inspect

from scripts import build_affidavit_coverage_review as module


def test_contested_lane_lexical_rules_are_quarantined_to_justification_hints() -> None:
    assert set(module._LEXICAL_HEURISTIC_HINT_RULES) == {"justification"}


def test_speech_act_and_actor_do_not_use_lexical_heuristic_groups() -> None:
    classify_src = inspect.getsource(module._classify_argumentative_role)
    claim_src = inspect.getsource(module._extract_claim_components)

    assert "_apply_lexical_heuristic_group" not in classify_src
    assert "_apply_lexical_heuristic_group" not in claim_src


def test_claim_state_does_not_promote_lexical_justification_hints() -> None:
    derive_src = inspect.getsource(module._derive_claim_state)

    assert "consent_signal" not in derive_src
    assert "authority_or_necessity_signal" not in derive_src
    assert "scope_limitation" not in derive_src


def test_canonical_promotion_uses_central_policy_gate() -> None:
    src = inspect.getsource(module)

    assert "promote_contested_claim(" in src


def test_truth_bearing_fields_are_assigned_from_claim_state_or_promotion() -> None:
    src = inspect.getsource(module)

    assert '"support_direction": claim_state["support_direction"]' in src
    assert '"conflict_state": claim_state["conflict_state"]' in src
    assert '"evidentiary_state": claim_state["evidentiary_state"]' in src
    assert '"operational_status": claim_state["operational_status"]' in src
    assert '"promotion_status": promotion["status"]' in src
    assert '"coverage_status": status' in src
