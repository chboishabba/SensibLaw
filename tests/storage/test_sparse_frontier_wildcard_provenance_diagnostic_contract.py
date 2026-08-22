from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diagnose_sparse_frontier_wildcard_provenance.py"


def test_wildcard_provenance_probe_is_read_only_and_interface_scoped() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "sensiblaw.sparse-frontier-wildcard-provenance-diagnostic.v0_1" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert '"provider_io_performed": False' in source
    assert '"semantic_mutation_performed": False' in source
    assert "demand_export.interface_id = %s" in source
    assert "demand.expected_target_kind = 1" in source


def test_probe_selects_only_true_four_axis_mask_zero_demands() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "demand.expected_factor_type_symbol_id IS NULL" in source
    assert "demand.expected_object_kind_symbol_id IS NULL" in source
    assert "demand.role_symbol_id IS NULL" in source
    assert "demand.lexical_symbol_id IS NULL" in source


def test_probe_reads_native_trigger_target_and_evidence_provenance() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "semantic_pnf_demand_trigger_occurrence_v1" in source
    assert "semantic_pnf_demand_target_occurrence_v1" in source
    assert "semantic_pnf_demand_occurrence_provenance" in source
    assert "occurrence_role = 3" in source
    assert "semantic_pnf_demand_occurrence_provenance_audit_v1" in source


def test_probe_keeps_legacy_occurrence_support_separate_from_native_provenance() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "semantic_pnf_demand_occurrence_support" in source
    assert "support.support_kind IN (1, 2)" in source
    assert '"with_legacy_strong_occurrence_support"' in source
    assert '"with_exact_trigger_occurrence"' in source
    assert '"with_exact_target_occurrence"' in source


def test_exact_target_coordinates_are_inventory_only_not_rewrites() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "exact_target_coordinate_inventory" in source
    assert "target.object_id" in source
    assert "object.object_kind_symbol_id" in source
    assert "object.head_symbol_id" in source
    assert "token.lemma_symbol_id" in source

    lowered = source.lower()
    assert "update execution.semantic_pnf_demand" not in lowered
    assert "insert into execution.semantic_pnf_demand" not in lowered
    assert "delete from execution.semantic_pnf_demand" not in lowered


def test_probe_preserves_missing_provenance_as_unknown() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "LEFT JOIN execution.semantic_pnf_demand_occurrence_provenance_audit_v1" in source
    assert "LEFT JOIN execution.semantic_pnf_demand_trigger_occurrence_v1" in source
    assert "LEFT JOIN execution.semantic_pnf_demand_target_occurrence_v1" in source
    assert 'if row[9] is not None else None' in source
