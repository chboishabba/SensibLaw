from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "benchmark_b1_1_a2_paragraph_authority_parity.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_b1_1_is_scoped_to_a2_and_transported_boundary_authority() -> None:
    source = _source()
    for required in (
        "semantic.normative_relation",
        "semantic.legal_condition",
        "semantic.legal_exception",
        "semantic.legal_transition",
        "semantic_pnf_parent_delta_projection",
        '"comparison_surface": "transported paragraph boundary authority"',
    ):
        assert required in source
    assert '"whole_paragraph_frontier_equality_claimed": False' in source


def test_b1_1_preserves_boundary_admission_distinction_for_objects() -> None:
    source = _source()
    assert "should_promote(obj.promotion_evidence, profile)" in source
    assert '"objects_require_sentence_boundary_promotion": True' in source
    assert "object_projection.child_interface_id" in source
    assert "factor_projection.child_interface_id" in source
    assert "semantic_pnf_hyperedge" in source


def test_b1_1_factor_and_residual_projection_use_authoritative_semantics() -> None:
    source = _source()
    assert "factor.factor_type_symbol_id" in source
    assert "factor.predicate_symbol_id" in source
    assert "demand.expected_factor_type_symbol_id" in source
    assert "demand.residual_type_symbol_id" in source
    assert 'keys["factor"]' in source
    assert 'keys["demand"]' in source


def test_b1_1_transport_fusion_has_no_source_interior_rescan() -> None:
    source = _source()
    assert "transport_sentence_delta_to_paragraph(" in source
    assert "fuse_paragraph_deltas(" in source
    assert "source_interior_rescans += transported.work.source_token_rescan_count" in source
    assert "source_interior_rescans += fused.work.source_token_rescan_count" in source
    assert '"zero_source_interior_rescan"' in source


def test_b1_1_is_read_only_and_does_not_claim_later_reconciliation() -> None:
    source = _source()
    lowered = source.casefold()
    assert "set transaction read only" in lowered
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered
    assert '"later_parent_reconciliation_in_scope": False' in source
    assert '"actor_profiles_in_scope": False' in source
    assert '"resolved_demands_in_scope": False' in source
    assert '"global_lookup_in_scope": False' in source
