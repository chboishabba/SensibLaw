from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_broader_corpus_diagnostics import build_diagnostics


def test_build_au_broader_corpus_diagnostics(tmp_path: Path) -> None:
    payload = build_diagnostics(tmp_path)

    artifact_path = Path(payload["artifact_path"])
    summary_path = Path(payload["summary_path"])

    assert artifact_path.exists()
    assert summary_path.exists()

    diagnostics = json.loads(artifact_path.read_text(encoding="utf-8"))
    summary = diagnostics["summary"]

    assert diagnostics["version"] == "au_broader_corpus_diagnostics_v1"
    assert summary["source_family_count"] == 4
    assert summary["workflow_kind_count"] == 2
    assert summary["transcript_semantic_bundle_count"] == 3
    assert summary["fact_count_total"] == 13
    assert summary["observation_count_total"] == 40
    assert summary["review_queue_count_total"] == 11
    assert summary["known_raw_transcript_file_count"] >= 4
    assert summary["peak_pressure_bundle"] == "wave5:real_transcript_false_coherence_v1"

    workflow_kinds = {row["workflow_kind"] for row in diagnostics["workflow_summaries"]}
    assert workflow_kinds == {"au_semantic", "transcript_semantic"}

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "AU Broader Corpus Diagnostics Summary" in summary_text
    assert "wave1:real_au_procedural_v1" in summary_text
    assert "wave5:real_transcript_false_coherence_v1" in summary_text
