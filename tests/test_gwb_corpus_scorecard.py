from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_corpus_scorecard import build_corpus_scorecard


def test_build_gwb_corpus_scorecard_artifact(tmp_path: Path) -> None:
    payload = build_corpus_scorecard(tmp_path)

    slice_path = Path(payload["slice_path"])
    summary_path = Path(payload["summary_path"])

    assert slice_path.exists()
    assert summary_path.exists()

    slice_payload = json.loads(slice_path.read_text(encoding="utf-8"))
    scorecard = payload["scorecard"]

    assert scorecard["destination"] == "complete_gwb_topic_understanding"
    assert scorecard["current_stage"] == "source_family_inventory_checkpoint"
    assert scorecard["source_family_count"] == 4
    assert scorecard["checked_handoff_promoted_relation_count"] == 19
    assert scorecard["public_bios_manifest_document_count"] == 9
    assert scorecard["public_bios_timeline_event_count"] == 9
    assert scorecard["corpus_timeline_event_count"] == 320
    assert scorecard["corpus_aao_event_count"] == 260
    assert scorecard["local_book_file_count"] == 4

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Corpus Scorecard Summary" in summary_text
    assert "checked_handoff" in summary_text
    assert "local_books" in summary_text

    families = {row["family"] for row in slice_payload["slice"]["source_family_inventory"]}
    assert families == {"checked_handoff", "public_bios_pack", "corpus_timeline", "local_books"}
