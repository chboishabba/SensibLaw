from __future__ import annotations

from src.reporting.structure_report import TextUnit, build_source_comparison_report, emit_comparison_summary


def test_structure_corpus_comparison_splits_per_source():
    units = [
        TextUnit("c1", "chat-run", "chat_test_db", "User: run `pytest -q` on ./SensibLaw/tests/test_lexeme_layer.py"),
        TextUnit("ctx1", "ctx-file", "context_file", "# Heading\n- outputs/rom/rom_samples_L0.json"),
        TextUnit("t1", "transcript-file", "transcript_file", "1/1/21, 10:00 AM - Alice: Hello"),
    ]
    payload = build_source_comparison_report(units, top_n=5)
    assert "overall" in payload
    assert len(payload["per_source"]) == 3
    by_id = {row["source_id"]: row for row in payload["per_source"]}
    assert by_id["chat-run"]["source_type"] == "chat_test_db"
    assert "command_ref" in by_id["chat-run"]["structural_kind_counts"]
    assert "message_boundary_ref" in by_id["ctx-file"]["structural_kind_counts"]
    assert "speaker_ref" in by_id["transcript-file"]["structural_kind_counts"]


def test_comparison_summary_emits_side_by_side_rows():
    units = [
        TextUnit("c1", "chat-run", "chat_test_db", "User: run `pytest -q` on ./SensibLaw/tests/test_lexeme_layer.py"),
        TextUnit("ctx1", "ctx-file", "context_file", "# Heading\n- outputs/rom/rom_samples_L0.json"),
    ]
    payload = build_source_comparison_report(units, top_n=3)
    summary = emit_comparison_summary(payload, top_n=3)
    assert "source comparison:" in summary
    assert "chat-run | chat_test_db" in summary
    assert "ctx-file | context_file" in summary
