from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "171_setwise_demand_occurrence_provenance.sql"
).read_text(encoding="utf-8")


def test_legacy_occurrence_row_trigger_is_retired() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_producer" in SQL
    assert "FOR EACH ROW" not in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2


def test_batch_keeps_unique_producer_gate_and_exact_token_scope() -> None:
    assert "HAVING count(*)=1" in SQL
    assert "factor.region_id=demand.source_region_id" in SQL
    assert "token.lemma_symbol_id=demand.lexical_symbol_id" in SQL
    assert "token.run_ref=demand.region_run_ref" in SQL
    assert "token.document_ref=demand.region_document_ref" in SQL
    assert "token.run_ref=producer.region_run_ref" in SQL
    assert "token.document_ref=producer.region_document_ref" in SQL
    assert "token.start_char>=demand.region_start_char" in SQL
    assert "token.end_char<=demand.region_end_char" in SQL


def test_target_requires_explicit_role_rule_and_unique_exact_support() -> None:
    assert "semantic_pnf_demand_target_role_rule" in SQL
    assert "edge.role_symbol_id=rule.target_role_symbol_id" in SQL
    assert "support.object_id=edge.object_id" in SQL
    # one HAVING is producer uniqueness, the other is target pair uniqueness
    assert SQL.count("HAVING count(*)=1") >= 2


def test_evidence_support_is_relation_ranked_not_looped() -> None:
    assert "row_number() OVER" in SQL
    assert "ORDER BY support.ordinal,support.token_id" in SQL
    assert "FOR evidence_row IN" not in SQL
    assert "register_numeric_pnf_demand_occurrence(" not in SQL


def test_only_numeric_factor_provenance_is_retracted_on_recompile() -> None:
    assert "producer_ref LIKE 'numeric-factor:%'" in SQL
    assert "Provenance registered by other explicit producer APIs remains untouched" in SQL


def test_batch_runs_after_demand_normalizers() -> None:
    assert "CREATE TRIGGER zzzz_semantic_pnf_demand_occurrence_insert_batch" in SQL
    assert "CREATE TRIGGER zzzz_semantic_pnf_demand_occurrence_update_batch" in SQL
