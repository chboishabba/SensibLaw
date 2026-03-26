from __future__ import annotations

import json
from pathlib import Path

from scripts.build_wikidata_structural_handoff import build_handoff_artifact


def test_build_wikidata_structural_handoff_artifact(tmp_path: Path) -> None:
    payload = build_handoff_artifact(tmp_path)

    slice_path = Path(payload["slice_path"])
    summary_path = Path(payload["summary_path"])
    facts_path = Path(payload["facts_path"])
    rules_path = Path(payload["rules_path"])
    engine_path = Path(payload["engine_path"])
    scorecard_path = Path(payload["scorecard_path"])

    assert slice_path.exists()
    assert summary_path.exists()
    assert facts_path.exists()
    assert rules_path.exists()
    assert engine_path.exists()
    assert scorecard_path.exists()

    slice_payload = json.loads(slice_path.read_text(encoding="utf-8"))
    assert slice_payload["version"] == "wikidata_structural_handoff_v1"
    assert slice_payload["summary"]["qualifier_baseline_statement_count"] == 8
    assert slice_payload["summary"]["promoted_hotspot_pack_count"] == 3
    assert slice_payload["summary"]["held_hotspot_pack_count"] == 1
    assert slice_payload["summary"]["disjointness_case_count"] == 3
    assert slice_payload["summary"]["contradiction_case_count"] == 2
    assert slice_payload["qualifier_core"]["drift_case"]["severity"] == "medium"

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Wikidata Structural Handoff Narrative Summary" in summary_text
    assert "GNU and GNU Project remain visible as review pressure" in summary_text
    assert "working_fluid_contradiction is a real contradiction case" in summary_text

    facts_text = facts_path.read_text(encoding="utf-8")
    assert 'qualifier_import_baseline "kind" "qualifier_baseline"' in facts_text
    assert 'pack_software_entity_kind_collapse_pack_v0 "hold_reason" "awaiting_manifest_promotion"' in facts_text
    assert 'case_working_fluid_contradiction "case_status" "contradiction"' in facts_text

    rules_text = rules_path.read_text(encoding="utf-8")
    assert 'X "structural_case_ready_for_handoff" "true"' in rules_text
    assert 'X "needs_review_due_to_governance" "true"' in rules_text

    scorecard_payload = json.loads(scorecard_path.read_text(encoding="utf-8"))
    assert scorecard_payload["destination"] == "checked_wikidata_structural_understanding"
    assert scorecard_payload["current_stage"] == "checked_structural_handoff_checkpoint"
    assert scorecard_payload["promoted_hotspot_pack_count"] == 3
    assert scorecard_payload["held_hotspot_pack_count"] == 1
    assert scorecard_payload["contradiction_case_count"] == 2

    engine_payload = json.loads(engine_path.read_text(encoding="utf-8"))
    assert engine_payload["status"] in {"ok", "engine_unavailable"}
    if engine_payload["status"] == "ok":
        triples = {
            (row["subject"], row["predicate"], row["object"])
            for row in engine_payload.get("triples", [])
        }
        assert (
            "qualifier_import_baseline",
            "demonstrates_import_preservation",
            "true",
        ) in triples
        assert (
            "pack_software_entity_kind_collapse_pack_v0",
            "needs_review_due_to_governance",
            "true",
        ) in triples
        assert (
            "case_working_fluid_contradiction",
            "needs_review_due_to_structure",
            "true",
        ) in triples
