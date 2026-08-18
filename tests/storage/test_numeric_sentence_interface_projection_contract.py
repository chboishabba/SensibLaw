from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/storage/postgres/numeric_sentence_admission.py"


def test_interface_exports_and_lookups_are_stage_set_projections() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    interface_tail = source.split("interface_id = int(cursor.fetchone()[0])", 1)[1]
    assert "cursor.executemany" not in interface_tail
    assert "INSERT INTO execution.semantic_pnf_interface_export" in interface_tail
    assert "INSERT INTO execution.semantic_pnf_interface_lookup" in interface_tail
    assert "FROM tmp_numeric_sentence_object AS stage" in interface_tail
    assert "FROM tmp_numeric_sentence_factor AS stage" in interface_tail
    assert "FROM tmp_numeric_sentence_demand AS stage" in interface_tail


def test_promoted_object_rank_is_compressed_while_other_ranks_keep_stage_order() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    interface_tail = source.split("interface_id = int(cursor.fetchone()[0])", 1)[1]
    assert "row_number() OVER (ORDER BY stage.ordinal) - 1" in interface_tail
    assert "stage.ordinal" in interface_tail
    assert "WHERE stage.promoted" in interface_tail


def test_python_does_not_reconstruct_slot_object_or_lookup_row_maps() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "object_id_by_token" not in source
    assert "lookup_rows" not in source
    assert "WITH object_choice AS" in source
    assert "ORDER BY source_token_id, ordinal DESC" in source


def test_demand_lexical_lookup_preserves_old_truthy_boundary() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "stage.lexical_symbol_id IS NOT NULL" in source
    assert "stage.lexical_symbol_id <> 0" in source
    assert "COALESCE(stage.expected_factor_type_symbol_id, 0)" in source
