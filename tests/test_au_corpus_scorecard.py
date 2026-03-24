from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_corpus_scorecard import build_corpus_scorecard


def test_build_au_corpus_scorecard_artifact(tmp_path: Path) -> None:
    payload = build_corpus_scorecard(tmp_path)

    slice_path = Path(payload["slice_path"])
    summary_path = Path(payload["summary_path"])

    assert slice_path.exists()
    assert summary_path.exists()

    slice_payload = json.loads(slice_path.read_text(encoding="utf-8"))
    scorecard = payload["scorecard"]

    assert scorecard["destination"] == "broader_au_corpus_understanding"
    assert scorecard["current_stage"] == "real_bundle_coverage_checkpoint"
    assert scorecard["included_real_bundle_count"] == 4
    assert scorecard["workflow_kind_count"] == 2
    assert scorecard["fact_count_total"] == 13
    assert scorecard["observation_count_total"] == 40
    assert scorecard["review_queue_count_total"] == 11
    assert scorecard["known_raw_transcript_file_count"] >= 4

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "AU Corpus Scorecard Summary" in summary_text
    assert "wave1:real_au_procedural_v1" in summary_text
    assert "wave5:real_transcript_professional_handoff_v1" in summary_text

    assert slice_payload["slice"]["summary"]["included_real_bundle_count"] == 4
    assert len(slice_payload["slice"]["bundle_inventory"]) == 4
    assert "transcript_semantic" in slice_payload["slice"]["included_workflow_kinds"]
    assert "au_semantic" in slice_payload["slice"]["included_workflow_kinds"]
