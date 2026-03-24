from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_zelph_handoff import build_handoff_artifact


def test_build_gwb_zelph_handoff_artifact(tmp_path: Path) -> None:
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
    assert slice_payload["version"] == "gwb_public_handoff_v1"
    assert slice_payload["summary"]["selected_promoted_relation_count"] >= 10
    assert slice_payload["summary"]["selected_seed_lane_count"] == 11
    assert slice_payload["summary"]["unresolved_surface_count"] >= 3

    predicates = {
        row["predicate_key"] for row in slice_payload["selected_promoted_relations"]
    }
    assert {"nominated", "confirmed_by", "signed", "vetoed", "ruled_by"} <= predicates

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "What the system recovered cleanly" in summary_text
    assert "George W. Bush nominated John Roberts." in summary_text
    assert "nominated John Roberts" in summary_text
    assert "## What the system refused to overresolve" in summary_text

    facts_text = facts_path.read_text(encoding="utf-8")
    assert 'actor_george_w_bush "nominated" actor_john_roberts' in facts_text
    assert 'gwb_us_law_iraq_2002_authorization "support_kind" "broad_cue"' in facts_text

    rules_text = rules_path.read_text(encoding="utf-8")
    assert 'actor_george_w_bush "executive_public_law_action" X' in rules_text
    assert 'X "needs_review_due_to_ambiguity" "true"' in rules_text

    scorecard_payload = json.loads(scorecard_path.read_text(encoding="utf-8"))
    assert scorecard_payload["destination"] == "complete_gwb_topic_understanding"
    assert scorecard_payload["current_stage"] == "checked_public_handoff_checkpoint"
    assert scorecard_payload["promoted_relation_count"] >= 10
    assert scorecard_payload["candidate_only_seed_lane_count"] >= 0
    assert scorecard_payload["matched_seed_lane_count"] >= 10
    assert scorecard_payload["broad_cue_seed_lane_count"] >= 1
    assert scorecard_payload["direct_support_seed_lane_count"] >= 1

    engine_payload = json.loads(engine_path.read_text(encoding="utf-8"))
    assert engine_payload["status"] in {"ok", "engine_unavailable"}
    if engine_payload["status"] == "ok":
        triples = {
            (row["subject"], row["predicate"], row["object"])
            for row in engine_payload.get("triples", [])
        }
        assert (
            "actor_george_w_bush",
            "executive_public_law_action",
            "actor_john_roberts",
        ) in triples
        assert (
            "gwb_us_law_iraq_2002_authorization",
            "needs_review_due_to_ambiguity",
            "true",
        ) in triples
