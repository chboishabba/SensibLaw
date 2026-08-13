from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M122 = (ROOT / "database/postgres_migrations/122_demand_occurrence_support.sql").read_text()
M123 = (ROOT / "database/postgres_migrations/123_h9_entity_bearing_from_occurrence.sql").read_text()
M124 = (ROOT / "database/postgres_migrations/124_h9_entity_label_from_occurrence.sql").read_text()
M125 = (ROOT / "database/postgres_migrations/125_source_object_from_occurrence_support.sql").read_text()
M126 = (ROOT / "database/postgres_migrations/126_producer_specific_occurrence_support.sql").read_text()
M127 = (ROOT / "database/postgres_migrations/127_occurrence_projection_and_shape_audit.sql").read_text()


def test_occurrence_carrier_distinguishes_strong_and_legacy_support() -> None:
    assert "support_kind IN (1,2,9)" in M122
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M122
    assert "support_kind IN (1,2)" in M122
    assert "support_kind=9" in M122


def test_lexical_producer_does_not_require_missing_role() -> None:
    assert "export.interface_id=demand.source_interface_id" in M126
    assert "export.key_symbol_id=demand.lexical_symbol_id" in M126
    assert "demand.role_symbol_id IS NULL" in M126
    assert "OR export.role_symbol_id=demand.role_symbol_id" in M126
    assert "demand.lexical_symbol_id IS NOT NULL" in M126


def test_role_factor_producer_uses_role_and_optional_typed_narrowing() -> None:
    assert "edge.role_symbol_id=demand.role_symbol_id" in M126
    assert "demand.expected_factor_type_symbol_id IS NULL" in M126
    assert "factor.factor_type_symbol_id=demand.expected_factor_type_symbol_id" in M126
    assert "demand.expected_object_kind_symbol_id IS NULL" in M126
    assert "object.object_kind_symbol_id=demand.expected_object_kind_symbol_id" in M126
    assert "demand.role_symbol_id IS NOT NULL" in M126


def test_strong_refresh_preserves_legacy_kind9_rows() -> None:
    delete_clause = M126.split("-- Lexical producer", 1)[0]
    assert "DELETE FROM execution.semantic_pnf_demand_occurrence_support" in delete_clause
    assert "support_kind IN (1,2)" in delete_clause
    assert "support_kind=9" not in delete_clause
    assert "demand.source_object_id IS NOT NULL" in M126


def test_strong_support_has_no_text_or_regex_semantics() -> None:
    lowered = M126.lower()
    assert "symbol_text" not in lowered
    assert "regexp" not in lowered
    assert " regex" not in lowered
    assert " like " not in lowered


def test_h9_entity_views_start_from_strong_occurrence_support() -> None:
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M123
    assert "demand.source_object_id" not in M123
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M124
    assert "demand.source_object_id" not in M124


def test_legacy_source_object_semantics_are_restored() -> None:
    assert "CREATE OR REPLACE FUNCTION execution.resolve_numeric_pnf_demand_source_object" in M126
    assert "object.region_id=demand.source_region_id" in M126
    assert "object.head_symbol_id=demand.lexical_symbol_id" in M126
    trigger_tail = M126.split("CREATE TRIGGER semantic_pnf_demand_occurrence_support_refresh", 1)[1]
    assert "source_object_id" not in trigger_tail.split("-- Restore 090a semantics", 1)[0]


def test_unique_strong_projection_has_its_own_column() -> None:
    assert "ADD COLUMN IF NOT EXISTS occurrence_source_object_id BIGINT" in M127
    assert "count(DISTINCT support.object_id)=1" in M127
    assert "support.support_kind IN (1,2)" in M127
    assert "SET occurrence_source_object_id=resolved_object_id" in M127
    assert "legacy_source_object_id" in M127


def test_coordinate_shape_audit_represents_producer_split() -> None:
    assert "semantic_pnf_demand_coordinate_shape_v1" in M127
    assert "has_lexical" in M127
    assert "has_role" in M127
    assert "coordinate_shape" in M127


def test_legacy_source_object_is_not_h9_authority() -> None:
    assert "support_kind=9" in M122
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M123
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M124
