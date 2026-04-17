from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.composed_candidate_admissibility import evaluate_composed_candidate_admissibility, gate_composed_candidate_node


@dataclass
class _CandidateStub:
    payload: dict

    def to_dict(self) -> dict:
        return dict(self.payload)


def _complete_candidate_payload() -> dict:
    return {
        "kind": "proposition",
        "predicate_family": "authority_action",
        "slots": {
            "subject": {"value": "appellant", "content_refs": ["cr:1"]},
            "object": {"value": "high court", "content_refs": ["cr:2"]},
        },
        "content_refs": ["cr:1", "cr:2"],
        "authority_wrapper": {
            "wrapper_kind": "authority_wrapper",
            "claimed_kind": "proposition",
            "status": "valid",
            "allowed_kinds": ["proposition"],
            "allowed_sections": ["Judgment"],
            "allowed_genres": ["case"],
        },
        "status": "composed",
        "support_phi_ids": ["phi:1", "phi:2"],
        "span_refs": ["span:1", "span:2"],
        "provenance_receipts": [
            {"support_phi_id": "phi:1", "span_ref": "span:1", "content_ref": "cr:1"},
            {"support_phi_id": "phi:2", "span_ref": "span:2", "content_ref": "cr:2"},
        ],
        "section": "Judgment",
        "genre": "case",
        "section_genre_compatibility": {
            "status": "compatible",
            "section": "Judgment",
            "genre": "case",
        },
        "accepted_constraints": [
            {"constraint": "no_contradiction", "status": "accepted"},
        ],
    }


def test_gate_promotes_when_all_checks_are_explicit_and_consistent() -> None:
    result = evaluate_composed_candidate_admissibility(_CandidateStub(_complete_candidate_payload()))

    assert result["decision"] == "promote"
    assert result["reasons"] == []
    assert result["checks"] == {
        "provenance_complete": True,
        "wrapper_valid": True,
        "slot_content_consistent": True,
        "section_genre_compatibility": True,
        "accepted_constraints_contradiction_free": True,
    }


def test_gate_audits_when_compatibility_and_constraint_witnesses_are_missing() -> None:
    payload = _complete_candidate_payload()
    payload.pop("section_genre_compatibility")
    payload.pop("accepted_constraints")

    result = gate_composed_candidate_node(payload)

    assert result["decision"] == "audit"
    assert "missing_section_genre_witness" in result["reasons"]
    assert "missing_accepted_constraint_witness" in result["reasons"]
    assert result["checks"]["provenance_complete"] is True
    assert result["checks"]["wrapper_valid"] is True
    assert result["checks"]["slot_content_consistent"] is True


@pytest.mark.parametrize(
    ("mutator", "expected_reason"),
    [
        (lambda payload: payload["provenance_receipts"].pop(), "provenance_incomplete"),
        (lambda payload: payload["authority_wrapper"].update({"claimed_kind": "event"}), "wrapper_kind_mismatch"),
        (
            lambda payload: payload["slots"]["object"].update({"content_refs": ["cr:missing"]}),
            "slot_content_mismatch:object",
        ),
        (
            lambda payload: payload.__setitem__(
                "section_genre_compatibility",
                {"status": "incompatible", "section": "Judgment", "genre": "case"},
            ),
            "section_genre_incompatible",
        ),
        (
            lambda payload: payload.__setitem__(
                "accepted_constraints",
                [{"status": "denied", "result": "ruled"}],
            ),
            "accepted_constraint_contradiction",
        ),
    ],
)
def test_gate_abstains_for_hard_defects(mutator, expected_reason: str) -> None:
    payload = _complete_candidate_payload()
    mutator(payload)

    result = evaluate_composed_candidate_admissibility(payload)

    assert result["decision"] == "abstain"
    assert any(expected_reason in reason for reason in result["reasons"])
