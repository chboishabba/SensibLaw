from __future__ import annotations

from src.pnf.stage_build_keys import derive_stage_build_keys, stage_build_key


def test_stage_key_is_order_independent_over_declared_inputs() -> None:
    first = stage_build_key(
        "base_reduction",
        inputs=("proposal:b", "proposal:a"),
        contract_ref="reducer:v1",
        declaration_refs=("rule:2", "rule:1"),
    )
    second = stage_build_key(
        "base_reduction",
        inputs=("proposal:a", "proposal:b"),
        contract_ref="reducer:v1",
        declaration_refs=("rule:1", "rule:2"),
    )
    assert first == second


def test_legal_ir_contract_change_does_not_change_parser_key() -> None:
    common = dict(
        canonical_text_digest="text:1",
        parser_contract_ref="spacy:v1",
        observation_refs=("observation:1",),
        base_proposal_refs=("proposal:1",),
        base_factor_refs=("factor:1",),
        declaration_refs=("declaration:1",),
        derived_proposal_refs=("proposal:2",),
        materialized_factor_refs=("factor:2",),
        constraint_refs=("constraint:1",),
    )
    first = derive_stage_build_keys(
        **common,
        legal_ir_contract_ref="legal-ir:v1",
    )
    second = derive_stage_build_keys(
        **common,
        legal_ir_contract_ref="legal-ir:v2",
    )

    assert first.parser_key == second.parser_key
    assert first.constraint_fixed_point_key == second.constraint_fixed_point_key
    assert first.legal_ir_projection_key != second.legal_ir_projection_key
