from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_gwb_broader_corpus_checkpoint as checkpoint_module
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
    assert summary["distinct_promoted_relation_count"] >= 17
    assert summary["distinct_seed_lane_count"] == 13
    assert summary["new_relation_count_vs_checked_handoff"] >= 2
    assert summary["seed_lanes_supported_in_multiple_families"] >= 1

    source_families = {row["source_family"] for row in slice_payload["source_family_summaries"]}
    assert source_families == {"checked_handoff", "public_bios_timeline", "corpus_book_timeline"}
    braid = slice_payload["cross_source_event_braid"]
    assert braid["schema_version"] == "sl.cross_source_event_braid.v0_1"
    assert braid["summary"]["source_family_count"] == 2
    assert braid["summary"]["merged_event_count"] >= 2
    assert braid["summary"]["cross_document_ordering_edge_count"] >= 1

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Broader Corpus Checkpoint Summary" in summary_text
    assert "public_bios_timeline" in summary_text
    assert "corpus_book_timeline" in summary_text
    assert "GWB Timeline QC Report" in summary_text
    assert "Source Event Count" in summary_text

    qc_report_path = tmp_path / "gwb_timeline_qc_report.json"
    assert qc_report_path.exists()
    qc_report = json.loads(qc_report_path.read_text(encoding="utf-8"))
    assert qc_report["source_event_count"] >= 0
    assert qc_report["blocked_event_count"] >= 0
    assert qc_report["active_event_count"] >= 0
    assert qc_report["candidate_link_count"] >= 0
    assert qc_report["merged_event_count"] >= 0
    assert qc_report["ordering_edge_count"] >= 0
    assert qc_report["historical_time_order_edge_count"] >= 0
    assert qc_report["timeline_export_event_count"] >= 0

    human_json_path = tmp_path / "gwb_human_review_timeline.json"
    human_md_path = tmp_path / "gwb_human_review_timeline.md"
    assert human_json_path.exists()
    assert human_md_path.exists()

    human_md_text = human_md_path.read_text(encoding="utf-8")
    assert "# GWB Human Review Timeline Packet" in human_md_text
    assert "Historical Timeline Candidate" in human_md_text
    assert "Excluded / Non-Timeline Items" in human_md_text
    assert "Recommended Next Human Review Queue" in human_md_text

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
        row["predicate_key"] == "vetoed"
        and row["object"]["canonical_key"] == "legal_ref:stem_cell_research_enhancement_act"
        and row["source_families"] == ["checked_handoff"]
        for row in merged_relations
    )
    signed_row = next(
        row
        for row in merged_relations
        if row["predicate_key"] == "signed"
        and row["object"]["canonical_key"] == "legal_ref:no_child_left_behind_act"
    )
    assert signed_row["lineage_records"]
    assert any(record["event_id"] for record in signed_row["lineage_records"])
    assert any(record["source_path"] or record["source_url"] for record in signed_row["lineage_records"])
    assert signed_row["cross_source_braid_depth"] in {"complete", "partial", "candidate_only", "missing"}
    assert isinstance(signed_row["merged_event_ids"], list)
    assert isinstance(signed_row["ordering_edge_ids"], list)


def test_gwb_broader_corpus_checkpoint_uses_shared_repo_roots() -> None:
    source = inspect.getsource(checkpoint_module)

    assert "repo_root()" in source
    assert "sensiblaw_root()" in source
