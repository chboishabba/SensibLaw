from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/policy/postgres_corpus_compilation.py"


def test_postgres_document_worker_guards_numeric_progress() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "ActiveDocumentResourceGuard(" in source
    assert "GuardedDocumentProgress(document_progress, document_guard)" in source
    assert "progress=guarded_progress" in source
