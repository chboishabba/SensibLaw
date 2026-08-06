from pathlib import Path


MIGRATION_ROOT = Path("database/postgres_migrations")
MIGRATIONS = tuple(
    path
    for ordinal in range(40, 55)
    for path in sorted(MIGRATION_ROOT.glob(f"{ordinal:03d}_*.sql"))
)


def _source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)


def _migration(ordinal: int) -> str:
    matches = [path for path in MIGRATIONS if path.name.startswith(f"{ordinal:03d}_")]
    assert len(matches) == 1
    return matches[0].read_text(encoding="utf-8")


def test_numeric_hyperfabric_schema_contains_no_json_authority() -> None:
    assert len(MIGRATIONS) == 15
    source = _source().casefold()
    assert " json " not in source
    assert " jsonb" not in source
    assert "::json" not in source
    assert "json_build" not in source


def test_numeric_hyperfabric_schema_declares_compact_ids_and_skip_indexes() -> None:
    source = _source()
    for required in (
        "semantic_symbol",
        "symbol_id BIGINT",
        "kind_id SMALLINT",
        "semantic_morph_set",
        "sentence_id BIGINT",
        "token_id BIGINT",
        "head_token_id BIGINT",
        "semantic_pnf_region",
        "semantic_pnf_region_edge",
        "semantic_pnf_interface",
        "semantic_pnf_interface_ancestor",
        "distance_power SMALLINT",
        "semantic_pnf_interface_typed_ancestor",
        "semantic_pnf_object",
        "semantic_pnf_factor",
        "semantic_pnf_hyperedge",
        "semantic_pnf_demand",
        "semantic_pnf_visible_lookup",
        "semantic_pnf_global_lookup",
        "semantic_pnf_mdl_profile",
        "semantic_pnf_work_item",
    ):
        assert required in source


def test_numeric_parser_representation_excludes_legacy_text_refs() -> None:
    source = _source()
    assert "representation_version = 2" in source
    for legacy_column in (
        "orth_ref IS NULL",
        "lemma_ref IS NULL",
        "pos_ref IS NULL",
        "tag_ref IS NULL",
        "dependency_ref IS NULL",
    ):
        assert legacy_column in source
    assert "assign_numeric_parser_sentence_id" in source


def test_numeric_parser_head_projection_is_commit_checked() -> None:
    source = _source()
    for required in (
        "validate_numeric_parser_head_integrity",
        "CREATE CONSTRAINT TRIGGER semantic_parser_token_head_integrity",
        "DEFERRABLE INITIALLY DEFERRED",
        "has no committed dependency head",
        "lacks explicit self coordinates",
        "head coordinates do not identify head",
        "crosses sentence identity",
    ):
        assert required in source


def test_hierarchy_is_reductive_indexed_and_demand_driven() -> None:
    source = _source()
    for required in (
        "admit_numeric_pnf_interface_export",
        "promotion_threshold",
        "derive_numeric_sentence_mentions",
        "derive_numeric_region_recurrence",
        "semantic_pnf_recurrence_group",
        "semantic_pnf_demand_candidate",
        "plan_numeric_pnf_demand_candidates",
        "semantic_pnf_visible_demand_planning",
        "semantic_pnf_global_lookup",
        "nearest_common_pnf_interface",
        "rebuild_pnf_document_ancestors",
    ):
        assert required in source


def test_demand_planning_normalizes_keys_and_runs_set_wise() -> None:
    source = _migration(53)
    for required in (
        "semantic_pnf_demand_lookup_key",
        "semantic_pnf_demand_lookup_key_join_idx",
        "target_deduplicated AS",
        "PARTITION BY match.demand_id",
        "LEFT JOIN LATERAL",
        "DROP TRIGGER IF EXISTS semantic_pnf_demand_candidate_visibility",
    ):
        assert required in source
    assert "FOR demand_row IN" not in source
    assert "WITH RECURSIVE" not in source


def test_interface_lookup_requires_an_admitted_export_for_every_target_kind() -> None:
    source = _migration(54)
    for required in (
        "admit_numeric_pnf_interface_lookup",
        "export.interface_id = NEW.interface_id",
        "export.target_kind = NEW.target_kind",
        "export.target_id = NEW.target_id",
        "RETURN NULL",
        "DELETE FROM execution.semantic_pnf_interface_lookup",
    ):
        assert required in source
    assert "IF NEW.target_kind <> 1" not in source


def test_old_decorative_parser_work_triggers_are_removed() -> None:
    source = MIGRATIONS[0].read_text(encoding="utf-8")
    assert "DROP TRIGGER IF EXISTS semantic_parser_sentence_graph_work" in source
    assert "DROP TRIGGER IF EXISTS semantic_parser_document_graph_work" in source
    assert "enqueue_numeric_sentence_region" in source
