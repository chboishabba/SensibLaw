from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMISSION = ROOT / "src/storage/postgres/numeric_sentence_admission.py"


def test_interface_export_union_types_null_symbol_columns_as_bigints() -> None:
    source = ADMISSION.read_text(encoding="utf-8")
    interface_export = source.split(
        "INSERT INTO execution.semantic_pnf_interface_export", 1
    )[1].split("ON CONFLICT DO NOTHING", 1)[0]

    assert interface_export.count("NULL::BIGINT") == 5
