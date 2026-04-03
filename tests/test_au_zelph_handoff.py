from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_zelph_handoff import build_handoff_artifact


def test_build_au_zelph_handoff_artifact(tmp_path: Path) -> None:
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
    assert slice_payload["version"] == "au_public_handoff_v1"
    assert slice_payload["summary"]["fact_count"] >= 3
    assert slice_payload["summary"]["observation_count"] >= 20
    assert slice_payload["summary"]["review_queue_count"] >= 3
    assert slice_payload["compiler_contract"]["lane"] == "au"
    assert slice_payload["compiler_contract"]["evidence_bundle"]["bundle_kind"] == "legal_hearing_bundle"
    assert slice_payload["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert slice_payload["promotion_gate"]["product_ref"] == "au_public_handoff_v1"
    assert len(slice_payload["selected_facts"]) >= 3

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "AU Public Handoff Narrative Summary" in summary_text
    assert "House v The King" in summary_text
    assert "Review queue items" in summary_text

    facts_text = facts_path.read_text(encoding="utf-8")
    assert '"signal_class" "procedural_outcome"' in facts_text
    assert '"review_status" "review_queue"' in facts_text

    rules_text = rules_path.read_text(encoding="utf-8")
    assert 'X "au_procedural_fact" "true"' in rules_text
    assert 'X "needs_review_due_to_procedural_pressure" "true"' in rules_text

    scorecard_payload = json.loads(scorecard_path.read_text(encoding="utf-8"))
    assert scorecard_payload["destination"] == "complete_au_topic_understanding"
    assert scorecard_payload["current_stage"] == "checked_real_workbench_checkpoint"
    assert scorecard_payload["fact_count"] >= 3
    assert scorecard_payload["operator_view_count"] >= 5

    engine_payload = json.loads(engine_path.read_text(encoding="utf-8"))
    assert engine_payload["status"] in {"ok", "engine_unavailable"}
    if engine_payload["status"] == "ok":
        triples = {
            (row["subject"], row["predicate"], row["object"])
            for row in engine_payload.get("triples", [])
        }
        assert any(pred == "au_procedural_fact" for _, pred, _ in triples)


def test_build_au_zelph_handoff_supports_multi_source_bundles(tmp_path: Path) -> None:
    source_a = Path("/home/c/Documents/code/ITIR-suite/itir-svelte/tests/fixtures/fact_review_wave1_real_au_demo_bundle.json")
    source_b = Path("/home/c/Documents/code/ITIR-suite/itir-svelte/tests/fixtures/fact_review_wave1_real_au_demo_bundle_b0babf.json")
    payload = build_handoff_artifact(
        tmp_path,
        source_bundle_paths=[source_a, source_b],
    )

    slice_payload = json.loads(Path(payload["slice_path"]).read_text(encoding="utf-8"))
    assert len(slice_payload["source_bundle_paths"]) == 2
    assert len(slice_payload["selected_facts"]) == 3
    assert slice_payload["summary"]["fact_count"] >= 3
    assert slice_payload["compiler_contract"]["evidence_bundle"]["source_count"] == 2
    assert slice_payload["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert all(len(row["source_bundles"]) == 2 for row in slice_payload["selected_facts"])
    assert any("fact:33bf5d1e2fbd3c36" == row["fact_id"] for row in slice_payload["selected_facts"])
