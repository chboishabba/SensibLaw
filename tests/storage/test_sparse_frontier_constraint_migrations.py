from pathlib import Path


MIGRATION_ROOT = Path("database/postgres_migrations")
STANDALONE_ACTORS = MIGRATION_ROOT / "066_standalone_actor_profiles.sql"
TYPED_CONSTRAINTS = (
    MIGRATION_ROOT / "067_typed_frontier_candidate_constraints.sql"
)


def test_standalone_actor_profiles_are_captured_set_wise() -> None:
    source = STANDALONE_ACTORS.read_text(encoding="utf-8")
    for required in (
        "capture_numeric_pnf_actor_export_profiles",
        "REFERENCING NEW TABLE AS inserted_export",
        "FOR EACH STATEMENT",
        "semantic_pnf_actor_export_profile",
        "role_symbol_id, factor_type_symbol_id, predicate_symbol_id",
        "0,\n           0,\n           0,",
        "ON CONFLICT (",
    ):
        assert required in source
    assert "FOR EACH ROW" not in source


def test_typed_candidate_constraints_filter_bounded_insertions() -> None:
    source = TYPED_CONSTRAINTS.read_text(encoding="utf-8")
    for required in (
        "filter_numeric_pnf_candidate_constraints",
        "REFERENCING NEW TABLE AS inserted_candidate",
        "FOR EACH STATEMENT",
        "semantic_pnf_typed_candidate_constraints",
        "semantic_pnf_demand_constraint",
        "semantic_pnf_actor_profile",
        "constraint_row.polarity = 1",
        "constraint_row.polarity = -1",
        "candidate.common_scope_interface_id",
        "candidate.source_interface_id",
        "candidate.target_kind",
    ):
        assert required in source
    assert "FOR EACH ROW" not in source
    assert "semantic_pnf_global_lookup" not in source
    assert "semantic_pnf_visible_lookup" not in source


def test_new_frontier_migrations_remain_numeric() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (STANDALONE_ACTORS, TYPED_CONSTRAINTS)
    ).casefold()
    assert " json " not in source
    assert "jsonb" not in source
    assert "::json" not in source
