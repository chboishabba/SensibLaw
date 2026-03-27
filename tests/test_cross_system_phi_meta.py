from __future__ import annotations

import jsonschema
import yaml
from pathlib import Path

from src.cross_system_phi_meta import build_default_phi_meta_contract, validate_phi_meta


def _load_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.cross_system_phi_meta.v1.schema.yaml").read_text(encoding="utf-8"))


def test_default_phi_meta_contract_validates_against_schema() -> None:
    contract = build_default_phi_meta_contract(left_system="au_hca", right_system="us_exec_judicial")
    jsonschema.validate(contract, _load_schema())


def test_phi_meta_blocks_structurally_similar_authority_mismatch() -> None:
    contract = build_default_phi_meta_contract(left_system="au_hca", right_system="us_exec_judicial")
    result = validate_phi_meta(
        left_record={
            "subject_kind": "actor",
            "object_kind": "actor",
            "predicate_key": "appealed",
            "rule_type": "review_relation",
            "subject_key": "actor:appellant",
            "object_key": "actor:high_court_of_australia",
            "promotion_status": "promoted_true",
            "source_char_start": 0,
            "source_char_end": 50,
        },
        right_record={
            "subject_kind": "actor",
            "object_kind": "actor",
            "predicate_key": "confirmed_by",
            "rule_type": "governance_action",
            "subject_key": "actor:john_roberts",
            "object_key": "actor:u_s_senate",
            "promotion_status": "promoted_true",
            "source_char_start": 0,
            "source_char_end": 50,
        },
        contract=contract,
    )

    assert result["allowed"] is False
    assert "authority_relation_incompatible" in result["violations"]
    assert result["witness"]["authority_alignment"]["relation"] == "incompatible"
    assert result["witness"]["constraint_check"]["status"] == "incompatible"


def test_phi_meta_allows_conditionally_admissible_judicial_to_executive_pair() -> None:
    contract = build_default_phi_meta_contract(left_system="au_hca", right_system="us_exec_judicial")
    result = validate_phi_meta(
        left_record={
            "subject_kind": "actor",
            "object_kind": "legal_ref",
            "predicate_key": "challenged",
            "rule_type": "review_relation",
            "subject_key": "actor:plaintiff",
            "object_key": "legal_ref:native_title_new_south_wales_act_1994",
            "promotion_status": "promoted_true",
            "source_char_start": 0,
            "source_char_end": 50,
        },
        right_record={
            "subject_kind": "actor",
            "object_kind": "legal_ref",
            "predicate_key": "signed",
            "rule_type": "executive_action",
            "subject_key": "actor:george_w_bush",
            "object_key": "legal_ref:military_commissions_act_of_2006",
            "promotion_status": "promoted_true",
            "source_char_start": 0,
            "source_char_end": 50,
        },
        contract=contract,
    )

    assert result["allowed"] is True
    assert result["constraint_status"] == "conditional"
    assert result["meta_score"] >= 0.72
    assert result["witness"]["type_alignment"]["relation"] == "exact"
    assert result["witness"]["authority_alignment"]["relation"] == "analogue"
    assert result["witness"]["role_alignments"][0]["relation"] == "exact"
