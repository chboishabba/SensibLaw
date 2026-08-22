from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diagnose_sparse_frontier_composite_signatures.py"


def test_composite_signature_diagnostic_is_read_only_counterfactual() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "sensiblaw.sparse-frontier-composite-signature-diagnostic.v0_1" in source
    assert "_DIRECT_OBJECT_CANDIDATE" in source
    assert "_INDEXED_OBJECT_CANDIDATE" in source
    assert "_COMPOSITE_OBJECT_CANDIDATE" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "EXCEPT ALL" in source
    assert "exact_multiset_parity" in source


def test_composite_signature_uses_one_four_axis_mask_and_exact_lexical_disjunction() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    # Four optional object-candidate axes -> sixteen finite masks.
    assert "generate_series(0, 15)" in source
    assert "THEN 8 ELSE 0" in source
    assert "THEN 4 ELSE 0" in source
    assert "THEN 2 ELSE 0" in source
    assert "THEN 1 ELSE 0" in source

    # Historical lexical semantics are head OR predicate.  UNION suppresses the
    # duplicate posting if both semantic coordinates are equal.
    assert "SELECT profile.head_symbol_id::BIGINT" in source
    assert "SELECT profile.predicate_symbol_id::BIGINT" in source
    assert "UNION\n       SELECT profile.predicate_symbol_id::BIGINT" in source


def test_composite_signature_join_is_conjunctive_not_unary_posthoc_intersection() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "profile.mask = demand.mask" in source
    assert "profile.factor_key = demand.factor_key" in source
    assert "profile.object_kind_key = demand.object_kind_key" in source
    assert "profile.role_key = demand.role_key" in source
    assert "profile.lexical_key = demand.lexical_key" in source

    # The counterfactual path must not rebuild conjunctive truth by grouping
    # independent unary matches.
    composite_start = source.index("_COMPOSITE_STATIC_MATCH =")
    composite_end = source.index("_COMPOSITE_OBJECT_CANDIDATE =")
    composite = source[composite_start:composite_end]
    assert "GROUP BY" not in composite
    assert "matched_count" not in composite


def test_zero_symbol_sentinel_is_fail_closed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "_ZERO_SYMBOL_GUARD" in source
    assert "refuses zero-valued semantic symbol ids" in source
    assert "_zero_symbol_guard(cursor, interface_id)" in source


def test_recursive_plan_receipt_exposes_rescan_shape_without_double_counting_buffers() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def _walk_plan" in source
    assert '"plan_node_count"' in source
    assert '"node_types"' in source
    assert '"max_actual_loops"' in source
    assert '"max_rows_removed_by_filter"' in source
    assert "Child sums would double-count inclusive metrics" in source
