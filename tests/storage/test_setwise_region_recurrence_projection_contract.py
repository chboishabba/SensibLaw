from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "database/postgres_migrations/177_setwise_region_recurrence_projection.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_recurrence_projection_replaces_per_candidate_loop_with_setwise_grouping() -> (
    None
):
    source = _source()

    assert (
        "CREATE OR REPLACE FUNCTION execution.derive_numeric_region_recurrence()"
        in source
    )
    assert "FOR candidate IN" not in source
    assert "WITH RECURSIVE descendants(region_id) AS MATERIALIZED" in source
    assert "GROUP BY mention.head_symbol_id" in source
    assert "HAVING count(*) >= 2" in source


def test_member_projection_is_one_partitioned_pass_over_recurrence_fibre() -> None:
    source = _source()

    assert "PARTITION BY recurrence.recurrence_id" in source
    assert "ORDER BY mention.start_char, mention.mention_id" in source
    assert "INSERT INTO execution.semantic_pnf_recurrence_member" in source
    assert "ON CONFLICT DO NOTHING" in source


def test_existing_recurrence_object_semantics_are_preserved() -> None:
    source = _source()

    assert "recurrence.object_id IS NULL" in source
    assert "int8send(recurrence.recurrence_id)" in source
    assert "int8send(NEW.region_id)" in source
    assert "int8send(selected_object_kind)" in source
    assert "DO UPDATE SET active = TRUE" in source


def test_recurrence_publication_remains_setwise_and_interface_local() -> None:
    source = _source()

    assert "INSERT INTO execution.semantic_pnf_object_mention_support" in source
    assert "INSERT INTO execution.semantic_pnf_interface_export" in source
    assert "INSERT INTO execution.semantic_pnf_interface_lookup" in source
    assert source.count("WHERE recurrence.region_id = NEW.region_id") >= 5
    assert "WHERE interface_id = selected_interface_id" in source


def test_sentence_region_gate_and_existing_trigger_authority_remain_unchanged() -> None:
    source = _source()

    assert "IF NEW.region_kind = 1" in source
    assert "NEW.closure_state NOT IN (2, 3)" in source
    assert "OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state" in source
    assert "CREATE TRIGGER semantic_pnf_region_recurrence_derivation" not in source
