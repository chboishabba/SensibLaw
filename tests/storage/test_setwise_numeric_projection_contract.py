from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "postgres_migrations"
POLICY = ROOT / "src" / "policy"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sentence_leaf_does_not_invoke_parent_frontier_reducer() -> None:
    sql = _text(MIGRATIONS / "146_skip_leaf_frontier_reduction.sql")
    guard = sql.index("IF NEW.region_kind IN (1, 2, 4, 9) THEN")
    reducer = sql.index("execution.rebuild_numeric_pnf_parent_frontier")
    assert guard < reducer


def test_sentence_provenance_keeps_generic_trigger_as_fail_closed_fallback() -> None:
    sql = _text(MIGRATIONS / "147_direct_sentence_demand_provenance.sql")
    policy = _text(POLICY / "producer_native_sentence_provenance.py")

    assert "FOR EACH ROW" in sql
    assert "sensiblaw.direct_sentence_demand_provenance" in sql
    assert "IS DISTINCT FROM 'on'" in sql
    assert "execution.record_numeric_pnf_demand_occurrence_provenance" in sql

    assert "tmp_numeric_sentence_demand" in policy
    assert "tmp_numeric_sentence_factor_support" in policy
    assert "tmp_numeric_sentence_factor_slot" not in policy or "semantic_pnf_hyperedge" in policy
    assert "HAVING count(*) = 1" in policy
    assert "semantic_pnf_demand_occurrence_provenance" in policy
    assert "set_config(" in policy


def test_demand_derivations_are_statement_level_transition_projections() -> None:
    sql = _text(MIGRATIONS / "148_setwise_demand_derivation_triggers.sql")

    assert "REFERENCING NEW TABLE AS inserted_demand" in sql
    assert "REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand" in sql
    assert sql.count("FOR EACH STATEMENT") == 2
    assert "semantic_pnf_horizon_work_queue" in sql
    assert "CROSS JOIN LATERAL" in sql
    assert "FOR EACH ROW" not in sql


def test_parser_sentence_region_work_is_one_statement_projection() -> None:
    sql = _text(MIGRATIONS / "149_setwise_sentence_region_work.sql")

    assert "REFERENCING NEW TABLE AS inserted_sentence" in sql
    assert "FOR EACH STATEMENT" in sql
    assert "FOR EACH ROW" not in sql
    assert "semantic_pnf_sentence_region" in sql
    assert "semantic_pnf_region_edge" in sql
    assert "semantic_pnf_work_item" in sql


def test_dependency_heads_are_resolved_statement_wise_and_fail_closed() -> None:
    sql = _text(MIGRATIONS / "150_setwise_numeric_dependency_heads.sql")
    policy = _text(POLICY / "numeric_parser_projection_hot_path.py")

    assert "REFERENCING NEW TABLE AS inserted_token" in sql
    assert "FOR EACH STATEMENT" in sql
    assert "HAVING count(head.token_id) <> 1" in sql
    assert "UPDATE execution.semantic_parser_token AS token" in sql
    assert "FOR EACH ROW" not in sql

    # The execution strategy may suppress only the redundant UPDATE payload.
    assert "original_project_heads(*args, **kwargs)" in policy
    assert "to_regprocedure(" in policy
    assert "head_token_id IS NULL" in policy
    assert "return ()" in policy


def test_reusable_sentence_stages_preserve_sentence_transaction_boundary() -> None:
    policy = _text(POLICY / "reusable_numeric_sentence_staging.py")

    assert policy.count("CREATE TEMP TABLE IF NOT EXISTS") == 5
    assert policy.count("ON COMMIT PRESERVE ROWS") == 5
    assert "TRUNCATE TABLE" in policy
    assert "ON COMMIT DROP" not in policy


def test_closure_strategy_installs_all_setwise_hot_paths() -> None:
    policy = _text(POLICY / "closure_hot_path_execution.py")

    for installer in (
        "install_numeric_parser_projection_hot_path()",
        "install_reusable_numeric_sentence_staging()",
        "install_producer_native_sentence_provenance()",
    ):
        assert installer in policy
