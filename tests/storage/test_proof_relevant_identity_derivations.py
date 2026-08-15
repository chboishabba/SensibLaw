from pathlib import Path


MIGRATION_ROOT = Path("database/postgres_migrations")
IDENTITY = MIGRATION_ROOT / "069_proof_relevant_identity_fibres.sql"
DERIVATIONS = MIGRATION_ROOT / "070_proof_relevant_factor_derivations.sql"
PUBLICATION = MIGRATION_ROOT / "071_sparse_root_derivation_publication.sql"
RETRACTION = MIGRATION_ROOT / "072_retractable_identity_and_external_alignment.sql"
EXTERNAL_HARDENING = MIGRATION_ROOT / "073_external_identity_ref_and_retraction.sql"
ADMISSION_INTEGRITY = MIGRATION_ROOT / "074_identity_admission_integrity.sql"
PERFORMANCE = MIGRATION_ROOT / "062_demand_planner_performance.sql"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_identity_is_a_separate_proof_relevant_layer() -> None:
    source = _source(IDENTITY)
    for required in (
        "semantic_pnf_canonical_entity",
        "semantic_pnf_identity_witness",
        "semantic_pnf_identity_witness_admission",
        "semantic_pnf_identity_witness_constraint",
        "semantic_pnf_identity_projection",
        "semantic_pnf_identity_fibre_member",
        "semantic_pnf_witnessed_hyperedge",
    ):
        assert required in source
    assert "parent_region_id" not in source
    assert "co-occurrence" in source
    assert "paragraph co-presence" in source


def test_only_explicit_unique_resolution_materialises_identity() -> None:
    source = _source(IDENTITY)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_identity_witnesses",
        1,
    )[1]
    assert "resolution.outcome_state = 2" in function
    assert "resolution.candidate_count = 1" in function
    assert "demand.source_object_id IS NOT NULL" in function
    assert "semantic_pnf_frontier_resolution" in function
    assert "anaphor_demand_resolution" in source
    assert "typed_demand_unique" in source


def test_ambiguous_identity_projection_fails_closed() -> None:
    source = _source(IDENTITY)
    view = source.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_identity_projection",
        1,
    )[1].split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_identity_fibre_member",
        1,
    )[0]
    assert "admission.admission_state = 2" in view
    assert "HAVING count(DISTINCT witness.target_entity_id) = 1" in view


def test_surface_identity_is_not_world_identity() -> None:
    source = _source(IDENTITY)
    assert "(1, 'surface_local', FALSE)" in source
    assert "(2, 'document_derived', FALSE)" in source
    assert "(3, 'corpus_derived', FALSE)" in source
    assert "(4, 'external_authority', TRUE)" in source
    assert "authority_class <> 4" in source
    assert "authority_namespace IS NOT NULL" in source
    assert "authority_identifier IS NOT NULL" in source


def test_identity_substitution_preserves_premises_and_witnesses() -> None:
    source = _source(DERIVATIONS)
    for required in (
        "semantic_pnf_factor_derivation_premise",
        "semantic_pnf_factor_derivation_argument",
        "source_object_id",
        "identity_entity_id",
        "identity_witness_ids",
        "identity-substitution:v1",
        "epistemic_level",
    ):
        assert required in source
    assert "identity_witness_ids IS NOT NULL" in source
    assert "cardinality(identity_witness_ids) > 0" in source


def test_factor_composition_remains_candidate_only() -> None:
    source = _source(DERIVATIONS)
    assert "shared-argument-composition:candidate-v1" in source
    assert "No semantic conclusion is licensed by this rule alone" in source
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_factor_composition_candidates",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_semantic_derivations",
        1,
    )[0]
    assert "semantic_pnf_factor_composition_candidate" in function
    assert "INSERT INTO execution.semantic_pnf_factor_derivation" not in function
    assert "candidate_rank < max_per_bridge" in function


def test_factor_composition_identity_bridge_requires_same_provenance_class() -> None:
    source = _source(DERIVATIONS)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_factor_composition_candidates",
        1,
    )[1]
    assert "right_edge.target_entity_id = left_edge.target_entity_id" in function
    assert "right_edge.authority_class = left_edge.authority_class" in function
    assert "right_edge.object_id <> left_edge.object_id" in function


def test_later_publication_migration_restores_root_only_global_lookup() -> None:
    assert PERFORMANCE.is_file()
    source = _source(PUBLICATION)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_ids",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_ids",
        1,
    )[0]
    assert "region.region_kind = 10" in function
    assert "lookup.interface_id = root_interface_id" in function
    assert "global.interface_id <> root_interface_id" in function
    assert "interface.closure_state IN (2, 3)" in function
    assert PUBLICATION.name > PERFORMANCE.name


def test_later_publication_migration_converges_planner_semantics() -> None:
    source = _source(PUBLICATION)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_ids",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.refresh_pnf_visible_lookup",
        1,
    )[0]
    assert "reduce_numeric_pnf_document_frontiers" in function
    assert "semantic_pnf_global_lookup" not in function
    assert "LATERAL" not in function


def test_derivation_stage_runs_before_root_publication() -> None:
    source = _source(PUBLICATION)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_pnf_visible_lookup",
        1,
    )[1]
    derivation = function.index("refresh_numeric_pnf_semantic_derivations")
    global_lookup = function.index("refresh_pnf_global_lookup_ids")
    assert derivation < global_lookup
    assert "'proof_relevant_derivations'" in function


def test_document_identity_admission_is_retractable() -> None:
    source = _source(RETRACTION)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_identity_witnesses",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_identity_substitution_derivations",
        1,
    )[0]
    assert "admission_state = 4" in function
    assert "witness.authority_class = 2" in function
    assert "resolution.outcome_state = 2" in function
    assert "resolution.candidate_count = 1" in function
    assert "admission_state = 2" in function


def test_identity_substitutions_are_rebuilt_from_current_witnesses() -> None:
    source = _source(RETRACTION)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_identity_substitution_derivations",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_external_identity_alignment",
        1,
    )[0]
    assert function.index(
        "DELETE FROM execution.semantic_pnf_factor_derivation"
    ) < function.index("INSERT INTO execution.semantic_pnf_factor_derivation")
    assert "semantic_pnf_identity_projection" in function
    assert "identity_witness_ids" in function


def test_external_world_identity_requires_explicit_authority_admission() -> None:
    source = _source(EXTERNAL_HARDENING)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_external_identity_alignment",
        1,
    )[1]
    assert "selected_authority_namespace" in function
    assert "selected_authority_identifier" in function
    assert "        4," in function
    assert "        10," in function
    assert "semantic_pnf_identity_witness_admission" in function
    assert "paragraph" not in function.casefold()
    assert "similar" not in function.casefold()
    assert "semantic_pnf_global_lookup" not in function


def test_external_identity_ref_uses_unambiguous_byte_separator() -> None:
    source = _source(EXTERNAL_HARDENING)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_external_identity_alignment",
        1,
    )[1]
    assert "convert_to(selected_authority_namespace, 'UTF8')" in function
    assert "decode('00', 'hex')" in function
    assert "convert_to(selected_authority_identifier, 'UTF8')" in function
    assert "digest(" in function


def test_explicit_identity_retraction_refreshes_current_derivations() -> None:
    source = _source(EXTERNAL_HARDENING)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.retract_numeric_pnf_identity_witness",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_external_identity_alignment",
        1,
    )[0]
    assert "admission_state = 3" in function
    assert "refresh_numeric_pnf_identity_substitution_derivations" in function
    assert "refresh_numeric_pnf_factor_composition_candidates" in function
    assert "resolved_run_id" in function
    assert "resolved_document_id" in function


def test_external_identity_admission_refreshes_current_derivations() -> None:
    source = _source(EXTERNAL_HARDENING)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_external_identity_alignment",
        1,
    )[1]
    assert "refresh_numeric_pnf_identity_substitution_derivations" in function
    assert "refresh_numeric_pnf_factor_composition_candidates" in function
    assert "resolved_run_id" in function
    assert "resolved_document_id" in function


def test_accepted_identity_witness_requires_unique_matching_authority() -> None:
    source = _source(ADMISSION_INTEGRITY)
    function = source.split(
        "CREATE OR REPLACE FUNCTION execution.validate_numeric_pnf_identity_admission",
        1,
    )[1].split("DROP TRIGGER IF EXISTS semantic_pnf_identity_admission_integrity", 1)[0]
    assert "NEW.admission_state <> 2" in function
    assert "witness_candidate_count <> 1" in function
    assert "witness_authority_class <> entity_authority_class" in function
    assert "semantic_pnf_identity_admission_integrity" in source


def test_identity_projection_repeats_integrity_gate_fail_closed() -> None:
    source = _source(ADMISSION_INTEGRITY)
    view = source.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_identity_projection",
        1,
    )[1].split("-- An upgraded database may already contain", 1)[0]
    assert "entity.authority_class = witness.authority_class" in view
    assert "witness.candidate_count = 1" in view
    assert "HAVING count(DISTINCT witness.target_entity_id) = 1" in view


def test_identity_integrity_upgrade_supersedes_and_purges_stale_derivations() -> None:
    source = _source(ADMISSION_INTEGRITY)
    assert "admission_state = 4" in source
    assert "DELETE FROM execution.semantic_pnf_factor_derivation" in source
    assert "NOT EXISTS (" in source
    assert "DELETE FROM execution.semantic_pnf_factor_composition_candidate" in source
    assert "bridge_entity_id IS NOT NULL" in source


def test_proof_migrations_do_not_add_json_authority() -> None:
    source = "\n".join(
        _source(path).casefold()
        for path in (
            IDENTITY,
            DERIVATIONS,
            PUBLICATION,
            RETRACTION,
            EXTERNAL_HARDENING,
            ADMISSION_INTEGRITY,
        )
    )
    assert " json " not in source
    assert "jsonb" not in source
    assert "::json" not in source
