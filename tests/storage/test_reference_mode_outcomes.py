from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/075_reference_mode_outcomes.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_reference_modes_are_explicit_typed_demand_state() -> None:
    source = _source()
    for required in (
        "semantic_pnf_reference_mode",
        "(1, 'singular')",
        "(2, 'plural')",
        "(3, 'generic')",
        "(4, 'inapplicable')",
        "ADD COLUMN IF NOT EXISTS reference_mode",
        "REFERENCES execution.semantic_pnf_reference_mode(reference_mode)",
    ):
        assert required in source


def test_singular_preserves_solver_multiplicity_while_non_singular_is_distinct() -> None:
    source = _source()
    classifier = source.split(
        "CREATE OR REPLACE FUNCTION execution.classify_numeric_pnf_reference_outcome",
        1,
    )[1].split(
        "DROP TRIGGER IF EXISTS semantic_pnf_reference_outcome_classification",
        1,
    )[0]
    assert "selected_reference_mode = 1" in classifier
    assert "NEW.outcome_state := 5" in classifier  # plural
    assert "NEW.outcome_state := 4" in classifier  # generic
    assert "NEW.outcome_state := 6" in classifier  # inapplicable
    assert "NEW.selected_target_id := NULL" in classifier


def test_plural_requires_actual_candidates() -> None:
    source = _source()
    classifier = source.split(
        "IF selected_reference_mode = 2 THEN",
        1,
    )[1].split("ELSIF selected_reference_mode = 3", 1)[0]
    assert "NEW.candidate_count > 0" in classifier


def test_non_singular_reference_cannot_leave_scalar_demand_target() -> None:
    source = _source()
    aligner = source.split(
        "CREATE OR REPLACE FUNCTION execution.align_numeric_pnf_reference_demand_state",
        1,
    )[1]
    assert "selected_reference_mode IN (2, 3, 4)" in aligner
    assert "resolved_target_kind = NULL" in aligner
    assert "resolved_target_id = NULL" in aligner


def test_reference_mode_migration_adds_no_json_or_proximity_identity_surface() -> None:
    source = _source().casefold()
    assert "jsonb" not in source
    assert "::json" not in source
    assert "paragraph" not in source
    assert "co-occurrence" not in source
    assert "similarity" not in source
