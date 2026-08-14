from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M135 = (ROOT / "database/postgres_migrations/135_demand_trigger_target_occurrence.sql").read_text()
M136 = (ROOT / "database/postgres_migrations/136_demand_occurrence_registration_hardening.sql").read_text()
REPORT = (ROOT / "scripts/report_demand_target_provenance.py").read_text()


def test_carrier_splits_trigger_target_and_evidence_occurrences() -> None:
    assert "semantic_pnf_demand_occurrence_provenance" in M135
    assert "occurrence_role SMALLINT" in M135
    assert "occurrence_role=1" in M135
    assert "occurrence_role=2" in M135
    assert "occurrence_role=3" in M135
    assert "semantic_pnf_demand_trigger_occurrence_v1" in M135
    assert "semantic_pnf_demand_target_occurrence_v1" in M135
    assert "semantic_pnf_demand_evidence_occurrence_v1" in M135


def test_generic_registration_requires_explicit_role_and_exact_object_support() -> None:
    assert "register_numeric_pnf_demand_occurrence" in M135
    assert "selected_occurrence_role NOT IN (1,2,3)" in M135
    assert "semantic_pnf_object_token_support" in M135
    assert "support.token_id=selected_token_id" in M135
    assert "object.region_id=selected_source_region_id" in M135


def test_registration_is_document_scoped_not_offset_only() -> None:
    assert "token.run_ref=region.run_ref" in M136
    assert "token.document_ref=region.document_ref" in M136
    assert "token.start_char>=region.start_char" in M136
    assert "token.end_char<=region.end_char" in M136
    assert "verify_numeric_pnf_demand_occurrence_provenance" in M136


def test_factor_producer_uses_exact_support_token_for_trigger() -> None:
    assert "semantic_pnf_factor_token_support" in M135
    assert "factor.factor_type_symbol_id=NEW.expected_factor_type_symbol_id" in M135
    assert "token.lemma_symbol_id=NEW.lexical_symbol_id" in M135
    assert "producer_match_count<>1" in M135
    assert "NEW.demand_id,1::SMALLINT,selected_trigger_token_id" in M135


def test_factor_support_is_evidence_not_automatic_target() -> None:
    evidence = M135.split("Preserve all other exact factor-support tokens as evidence", 1)[1]
    evidence = evidence.split("SELECT rule.target_role_symbol_id", 1)[0]
    assert "3::SMALLINT" in evidence
    assert "2::SMALLINT" not in evidence


def test_target_requires_explicit_residual_to_role_rule() -> None:
    assert "semantic_pnf_demand_target_role_rule" in M135
    assert "legal_object_identity_unresolved" in M135
    assert "'legal_object'" in M135
    assert "condition_attachment_unresolved" in M135
    assert "exception_attachment_unresolved" in M135
    assert "norm_bearer_unresolved" in M135
    assert "No target-role rule means" in M135
    assert "selected_target_role_id IS NULL" in M135


def test_target_requires_unique_typed_factor_slot_and_exact_token_object() -> None:
    assert "edge.factor_id=selected_factor_id" in M135
    assert "edge.role_symbol_id=selected_target_role_id" in M135
    assert "support.object_id=edge.object_id" in M135
    assert "target_match_count<>1" in M135
    assert "NEW.demand_id,2::SMALLINT,selected_target_token_id" in M135


def test_migration_install_does_not_backfill_historical_demands() -> None:
    lowered = M135.lower()
    assert "historical demand rows" in lowered
    assert "not backfilled" in lowered
    assert "update execution.semantic_pnf_demand\n   set" not in lowered
    assert "insert into execution.semantic_pnf_demand_occurrence_provenance\n    select demand.demand_id" not in lowered


def test_recompile_path_fires_on_insert_and_existing_demand_update() -> None:
    assert "AFTER INSERT OR UPDATE OF" in M135
    assert "state,source_region_id,expected_factor_type_symbol_id" in M135
    assert "record_numeric_pnf_demand_occurrence_provenance" in M135


def test_h9_consumes_only_producer_target_occurrence() -> None:
    assert "semantic_pnf_demand_h9_target_support_v1" in M135
    safe = M135.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_demand_parser_entity_occurrence_v1",
        1,
    )[1]
    safe = safe.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1",
        1,
    )[0]
    assert "semantic_pnf_demand_h9_target_support_v1" in safe
    assert "semantic_pnf_demand_strong_occurrence_support_v1" not in safe
    assert "semantic_pnf_demand_trigger_occurrence_v1" not in safe


def test_historical_provider_origins_are_withdrawn_not_deleted() -> None:
    assert "UPDATE execution.semantic_pnf_consumer_external_need_origin" in M135
    assert "SET active=FALSE" in M135
    assert "DELETE FROM execution.semantic_pnf_consumer_external_need_origin" not in M135


def test_no_textual_nearest_noun_recovery_is_added() -> None:
    lowered = M135.lower()
    for forbidden in ("regexp", " regex", " like ", "ilike", "similar to"):
        assert forbidden not in lowered
    assert "nearby noun" in lowered


def test_live_report_is_no_provider_io_and_surfaces_trigger_target_split() -> None:
    assert "semantic_pnf_demand_trigger_occurrence_v1" in REPORT
    assert "semantic_pnf_demand_target_occurrence_v1" in REPORT
    assert "semantic_pnf_demand_h9_target_support_v1" in REPORT
    assert "semantic_pnf_demand_parser_entity_occurrence_v1" in REPORT
    assert '"provider_io_performed": False' in REPORT
