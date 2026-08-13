from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M122 = (ROOT / "database/postgres_migrations/122_demand_occurrence_support.sql").read_text()
M123 = (ROOT / "database/postgres_migrations/123_h9_entity_bearing_from_occurrence.sql").read_text()
M124 = (ROOT / "database/postgres_migrations/124_h9_entity_label_from_occurrence.sql").read_text()
M125 = (ROOT / "database/postgres_migrations/125_source_object_from_occurrence_support.sql").read_text()


def test_occurrence_carrier_distinguishes_strong_and_legacy_support() -> None:
    assert "support_kind IN (1,2,9)" in M122
    assert "support_kind IN (1,2)" in M122
    assert "support_kind=9" in M122
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M122


def test_strong_object_support_uses_exact_interface_key_and_role() -> None:
    assert "export.interface_id=demand.source_interface_id" in M122
    assert "export.key_symbol_id=demand.lexical_symbol_id" in M122
    assert "export.role_symbol_id=demand.role_symbol_id" in M122
    assert "export.target_kind=1" in M122
    assert "export.export_kind=1" in M122


def test_factor_slot_support_is_typed_and_role_exact() -> None:
    assert "factor.factor_type_symbol_id=demand.expected_factor_type_symbol_id" in M122
    assert "edge.role_symbol_id=demand.role_symbol_id" in M122
    assert "edge.factor_id=factor.factor_id" in M122
    assert "edge.object_id" in M122


def test_strong_support_has_no_text_or_regex_semantics() -> None:
    strong_prefix = M122.split("-- Retain the historical unique-region", 1)[0].lower()
    assert "symbol_text" not in strong_prefix
    assert "regexp" not in strong_prefix
    assert " regex" not in strong_prefix
    assert " like " not in strong_prefix


def test_h9_entity_views_start_from_strong_occurrence_support() -> None:
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M123
    assert "demand.source_object_id" not in M123
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in M124
    assert "demand.source_object_id" not in M124


def test_source_object_is_only_unique_projection_of_strong_support() -> None:
    assert "count(DISTINCT support.object_id)=1" in M125
    assert "support.support_kind IN (1,2)" in M125
    assert "object.head_symbol_id=demand.lexical_symbol_id" not in M125
    assert "source_region_id" not in M125


def test_legacy_source_object_is_not_h9_authority() -> None:
    assert "support_kind=9" in M122
    assert "support_kind IN (1,2)" in M123
    assert "support_kind IN (1,2)" in M125
