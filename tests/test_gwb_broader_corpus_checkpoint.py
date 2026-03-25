from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_broader_corpus_checkpoint import build_broader_checkpoint


def test_build_gwb_broader_corpus_checkpoint(tmp_path: Path) -> None:
    payload = build_broader_checkpoint(tmp_path)

    slice_path = Path(payload["slice_path"])
    summary_path = Path(payload["summary_path"])

    assert slice_path.exists()
    assert summary_path.exists()

    slice_payload = json.loads(slice_path.read_text(encoding="utf-8"))
    summary = slice_payload["summary"]

    assert slice_payload["version"] == "gwb_broader_corpus_checkpoint_v1"
    assert summary["source_family_count"] == 3
    assert summary["distinct_promoted_relation_count"] >= 18
    assert summary["distinct_seed_lane_count"] == 13
    assert summary["new_relation_count_vs_checked_handoff"] >= 3
    assert summary["seed_lanes_supported_in_multiple_families"] >= 5

    source_families = {row["source_family"] for row in slice_payload["source_family_summaries"]}
    assert source_families == {"checked_handoff", "public_bios_timeline", "corpus_book_timeline"}

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Broader Corpus Checkpoint Summary" in summary_text
    assert "public_bios_timeline" in summary_text
    assert "corpus_book_timeline" in summary_text

    merged_relations = slice_payload["merged_promoted_relations"]
    assert any(row["predicate_key"] == "nominated" for row in merged_relations)
    assert any(row["predicate_key"] in {"signed", "vetoed", "confirmed_by"} for row in merged_relations)
    assert any(
        row["predicate_key"] == "signed" and row["object"]["canonical_key"] == "legal_ref:no_child_left_behind_act"
        for row in merged_relations
    )
    assert any(
        row["predicate_key"] == "signed"
        and row["object"]["canonical_key"] == "legal_ref:northwestern_hawaiian_islands_marine_national_monument"
        for row in merged_relations
    )
    assert any(
        row["predicate_key"] == "ruled_by" and row["source_families"] == ["corpus_book_timeline"]
        for row in merged_relations
    )
    assert any(
        row["predicate_key"] == "vetoed"
        and row["object"]["canonical_key"] == "legal_ref:stem_cell_research_enhancement_act"
        and row["source_families"] == ["checked_handoff", "corpus_book_timeline"]
        for row in merged_relations
    )
