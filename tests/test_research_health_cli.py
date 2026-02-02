from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.storage.versioned_store import VersionedStore


def _build_store(tmp_path: Path) -> Path:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    try:
        meta1 = DocumentMetadata(
            jurisdiction="au",
            citation="[1992] HCA 23",
            date=date(1992, 1, 1),
            title="HCA 23",
        )
        meta2 = DocumentMetadata(
            jurisdiction="au",
            citation="[2000] HCA 1",
            date=date(2000, 1, 1),
            title="HCA 1",
        )
        doc1 = Document(meta1, "Doc text with [1992] HCA 23 and [2000] HCA 1.")
        doc2 = Document(meta2, "Second doc without new cites.")
        store.add_revision(store.generate_id(), doc1, meta1.date)
        store.add_revision(store.generate_id(), doc2, meta2.date)
    finally:
        store.close()
    return db


def _run_cli(db_path: Path) -> dict:
    cmd = ["python", "-m", "cli", "report", "research-health", "--db", str(db_path)]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout.strip())


def test_research_health_cli_matches_golden(tmp_path: Path) -> None:
    db = _build_store(tmp_path)
    actual = _run_cli(db)

    golden_path = Path(__file__).resolve().parent / "fixtures" / "research_health" / "report_small.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    # Drop size-sensitive fields to avoid environment-specific noise before comparing.
    for noisy_key in ("db_size_mb", "db_delta_mb_per_doc_mean"):
        actual.pop(noisy_key, None)

    filtered = {key: actual[key] for key in golden.keys()}
    assert filtered == golden
    assert actual.get("compression_ratio_mean", 0) > 0
    assert actual.get("tokens_per_document_mean", 0) > 0
