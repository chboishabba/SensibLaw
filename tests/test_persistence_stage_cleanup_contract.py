from __future__ import annotations

from pathlib import Path


def test_stage_hot_path_defers_cleanup_out_of_authority_transaction() -> None:
    source = Path("src/storage/postgres/work_conserving_stage_hot_path.py").read_text(
        encoding="utf-8"
    )
    complete = source.split("def complete_stage", 1)[1].split("def runtime_finish", 1)[0]
    assert "DELETE FROM execution.document_persistence_stage" not in complete
    assert "state_ref = 'published'" in complete


def test_cleanup_sweep_deletes_only_published_execution_rows() -> None:
    source = Path("src/storage/postgres/work_conserving_stage_hot_path.py").read_text(
        encoding="utf-8"
    )
    cleanup = source.split("def _maybe_cleanup_published_stages", 1)[1].split(
        "def install_work_conserving_stage_hot_path", 1
    )[0]
    assert "run.state_ref = 'published'" in cleanup
    assert "DELETE FROM execution.document_persistence_stage" in cleanup
    assert "SENSIBLAW_PERSISTENCE_CLEANUP_EVERY_DOCUMENTS" in source
