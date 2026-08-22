from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diagnose_sparse_frontier_mask_buckets.py"


def test_mask_bucket_probe_is_read_only_and_resumable() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "sensiblaw.sparse-frontier-mask-bucket-diagnostic.v0_1" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert 'action="append"' in source
    assert '"mask_bucket_summary"' in source
    assert '"complete_mask_set"' in source
    assert '"global_exact_parity"' in source


def test_mask_bucket_probe_generates_four_axis_mask_from_native_demand_columns() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"factor": 8' in source
    assert '"object_kind": 4' in source
    assert '"role": 2' in source
    assert '"lexical": 1' in source
    assert "expected_factor_type_symbol_id IS NOT NULL THEN 8" in source
    assert "expected_object_kind_symbol_id IS NOT NULL THEN 4" in source
    assert "role_symbol_id IS NOT NULL THEN 2" in source
    assert "lexical_symbol_id IS NOT NULL THEN 1" in source


def test_mask_specialised_lookup_uses_only_active_profile_equalities() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def _profile_join_conditions(mask: int)" in source
    assert "profile.interface_id = %s" in source
    assert (
        "profile.factor_type_symbol_id = demand.expected_factor_type_symbol_id"
        in source
    )
    assert (
        "profile.object_kind_symbol_id = demand.expected_object_kind_symbol_id"
        in source
    )
    assert "profile.role_symbol_id = demand.role_symbol_id" in source
    # The C2 lookup must not regenerate the 16x profile-signature relation.
    assert "generate_series(0, 15)" not in source
    assert "IS NOT DISTINCT FROM" not in source


def test_lexical_mask_split_preserves_profile_row_identity_before_union() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "predicate_hit AS" in source
    assert "head_hit AS" in source
    assert "profile.predicate_symbol_id = demand.lexical_symbol_id" in source
    assert "object.head_symbol_id = demand.lexical_symbol_id" in source
    assert "SELECT * FROM predicate_hit\n    UNION\n    SELECT * FROM head_hit" in source
    # Hidden profile coordinates remain in the UNION projection so two distinct
    # profile rows are not collapsed merely because their final candidate tuple
    # is observationally equal.
    assert "profile.object_kind_symbol_id" in source
    assert "profile.role_symbol_id" in source
    assert "profile.factor_type_symbol_id" in source
    assert "profile.predicate_symbol_id" in source


def test_mask_zero_remains_broad_and_no_missing_axis_is_negative_evidence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "Mask zero remains an explicit broad fallback" in source
    # Active predicates are conditionally added in Python; there is no SQL rule
    # requiring inactive coordinates to be NULL/zero on the profile side.
    assert "profile.factor_type_symbol_id IS NULL" not in source
    assert "profile.object_kind_symbol_id IS NULL" not in source
    assert "profile.role_symbol_id IS NULL" not in source


def test_per_mask_parity_is_exact_and_fingerprint_is_only_a_hint() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "EXCEPT ALL" in source
    assert '"mask_exact_parity"' in source
    assert '"exact_multiset_parity"' in source
    assert "hashtextextended" in source
    assert "cheap routing hint, not semantic authority" in source
    assert "Exact EXCEPT ALL" in source


def test_mask_probe_records_physical_plan_shape_and_spill() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def _walk_plan" in source
    assert '"node_types"' in source
    assert '"temp_read_blocks"' in source
    assert '"temp_written_blocks"' in source
    assert '"max_actual_loops"' in source
    assert '"max_rows_removed_by_filter"' in source


def test_profile_posting_counts_are_mask_local_and_lexical_deduplicated() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def _mask_profile_posting_sql(mask: int)" in source
    assert '"mask_profile_posting_count"' in source
    assert "SELECT profile.predicate_symbol_id AS lexical_symbol_id" in source
    assert "SELECT object.head_symbol_id" in source
    assert "UNION" in source
