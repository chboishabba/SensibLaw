from pathlib import Path


MIGRATION_ROOT = Path("database/postgres_migrations")
IDENTITY = MIGRATION_ROOT / "069_proof_relevant_identity_fibres.sql"
DERIVATIONS = MIGRATION_ROOT / "070_proof_relevant_factor_derivations.sql"
PUBLICATION = MIGRATION_ROOT / "071_sparse_root_derivation_publication.sql"
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

    # The identity layer must never infer equality from paragraph membership.
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
        "CREATE OR REPLACE FUNCTION "
        "execution.refresh_numeric_pnf_factor_composition_candidates",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION "
        "execution.refresh_numeric_pnf_semantic_derivations",
        1,
    )[0]
    assert "semantic_pnf_factor_composition_candidate" in function
    assert "INSERT INTO execution.semantic_pnf_factor_derivation" not in function
    assert "candidate_rank < max_per_bridge" in function


def test_factor_composition_identity_bridge_requires_same_provenance_class() -> None:
    source = _source(DERIVATIONS)
    function = source.split(
        "CREATE OR REPLACE FUNCTION "
        "execution.refresh_numeric_pnf_factor_composition_candidates",
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
        "CREATE OR REPLACE FUNCTION execution.refresh_pnf_visible_lookup",
        1,
    )[0]
    assert "region.region_kind = 10" in function
    assert "lookup.interface_id = root_interface_id" in function
    assert "global.interface_id <> root_interface_id" in function
    assert "interface.closure_state IN (2, 3)" in function
    # This later migration intentionally supersedes the benchmark migration's
    # all-closed-interface materialisation on upgraded databases.
    assert PUBLICATION.name > PERFORMANCE.name


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


def test_proof_migrations_do_not_add_json_authority() -> None:
    source = "\n".join(
        _source(path).casefold()
        for path in (IDENTITY, DERIVATIONS, PUBLICATION)
    )
    assert " json " not in source
    assert "jsonb" not in source
    assert "::json" not in source
