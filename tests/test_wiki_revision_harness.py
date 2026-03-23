from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.text.similarity import simhash_hamming_distance, token_jaccard_similarity
from src.wiki_timeline.article_state import build_wiki_article_state
from src.wiki_timeline.revision_harness import build_revision_comparison_report


def _snapshot(*, title: str, revid: int, wikitext: str) -> dict:
    return {
        "wiki": "enwiki",
        "title": title,
        "revid": revid,
        "rev_timestamp": "2026-03-09T00:00:00Z",
        "source_url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        "fetched_at": "2026-03-09T00:00:10Z",
        "wikitext": wikitext,
    }


def _payload(*, title: str, revid: int, events: list[dict]) -> dict:
    return {
        "ok": True,
        "generated_at": "2026-03-09T00:00:20Z",
        "source_timeline": {"path": "dummy.json", "snapshot": _snapshot(title=title, revid=revid, wikitext="")},
        "source_entity": {
            "id": "source:test",
            "type": "wikipedia_article",
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            "version_hash": str(revid),
        },
        "events": events,
    }


def test_similarity_helpers_expose_distance_and_jaccard() -> None:
    assert token_jaccard_similarity("alpha beta", "alpha beta gamma") == 2 / 3
    assert simhash_hamming_distance("0f", "0f") == 0


def test_revision_harness_reports_no_material_graph_change_for_cosmetic_text() -> None:
    previous_snapshot = _snapshot(title="Example", revid=1, wikitext="Alpha beta")
    current_snapshot = _snapshot(title="Example", revid=2, wikitext="Alpha   beta")
    previous_payload = _payload(
        title="Example",
        revid=1,
        events=[
            {
                "event_id": "ev1",
                "text": "Alpha beta",
                "action": "meet",
                "actors": [{"label": "Alice"}],
                "objects": [{"title": "Bob"}],
                "steps": [{"action": "meet", "subjects": ["Alice"], "objects": [{"title": "Bob"}]}],
                "claim_bearing": False,
                "claim_step_indices": [],
                "attributions": [],
            }
        ],
    )
    current_payload = _payload(
        title="Example",
        revid=2,
        events=[
            {
                "event_id": "ev1",
                "text": "Alpha beta",
                "action": "meet",
                "actors": [{"label": "Alice"}],
                "objects": [{"title": "Bob"}],
                "steps": [{"action": "meet", "subjects": ["Alice"], "objects": [{"title": "Bob"}]}],
                "claim_bearing": False,
                "claim_step_indices": [],
                "attributions": [],
            }
        ],
    )

    report = build_revision_comparison_report(
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        previous_payload=previous_payload,
        current_payload=current_payload,
    )

    assert report["revisions"]["same_article"] is True
    assert report["graph_impact_summary"]["material_change"] is False
    assert report["state_delta_summary"]["changed_event_candidate_ids"] == []
    assert report["extraction_delta_summary"]["changed_event_ids"] == []
    assert report["issue_packets"] == []


def test_revision_harness_surfaces_epistemic_graph_and_state_delta() -> None:
    previous_snapshot = _snapshot(title="Example", revid=1, wikitext="Alice met Bob.")
    current_snapshot = _snapshot(title="Example", revid=2, wikitext="Alice reported Bob resigned.")
    previous_payload = _payload(
        title="Example",
        revid=1,
        events=[
            {
                "event_id": "ev1",
                "text": "Alice met Bob.",
                "action": "meet",
                "actors": [{"label": "Alice"}],
                "objects": [{"title": "Bob"}],
                "steps": [{"action": "meet", "subjects": ["Alice"], "objects": [{"title": "Bob"}]}],
                "claim_bearing": False,
                "claim_step_indices": [],
                "attributions": [],
            }
        ],
    )
    current_payload = _payload(
        title="Example",
        revid=2,
        events=[
            {
                "event_id": "ev1",
                "text": "Alice reported Bob resigned.",
                "action": "report",
                "actors": [{"label": "Alice"}],
                "objects": [{"title": "Bob"}],
                "steps": [
                    {
                        "action": "report",
                        "subjects": ["Alice"],
                        "objects": [{"title": "Bob resigned"}],
                        "claim_bearing": True,
                    }
                ],
                "claim_bearing": True,
                "claim_step_indices": [0],
                "attributions": [
                    {
                        "attributed_actor_id": "Alice",
                        "attribution_type": "direct_statement",
                        "source_entity_id": "source:test",
                        "step_index": 0,
                    }
                ],
            }
        ],
    )

    report = build_revision_comparison_report(
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        previous_payload=previous_payload,
        current_payload=current_payload,
        review_context={"ev1": {"wikidata_qids": ["Q42"]}},
    )

    assert report["graph_impact_summary"]["material_change"] is True
    assert report["state_delta_summary"]["changed_event_candidate_ids"] == ["ev1"]
    assert report["epistemic_delta_summary"]["added_claim_bearing_event_ids"] == ["ev1"]
    assert report["issue_packets"][0]["severity"] == "high"
    assert "epistemic" in report["issue_packets"][0]["surfaces"]
    assert "claims" in report["issue_packets"][0]["state_change_summary"]
    assert report["issue_packets"][0]["changed_observation_ids"]
    assert report["issue_packets"][0]["review_context"] == {"wikidata_qids": ["Q42"]}


def test_revision_harness_surfaces_anchor_status_changes_from_canonical_state() -> None:
    previous_state = build_wiki_article_state(
        _snapshot(
            title="Example",
            revid=1,
            wikitext="Jane patted the cat after lunch.",
        ),
        no_spacy=True,
    )
    current_state = build_wiki_article_state(
        _snapshot(
            title="Example",
            revid=2,
            wikitext="On May 5, 2021, Jane patted the cat after lunch.",
        ),
        no_spacy=True,
    )

    report = build_revision_comparison_report(
        previous_snapshot=_snapshot(title="Example", revid=1, wikitext="Jane patted the cat after lunch."),
        current_snapshot=_snapshot(title="Example", revid=2, wikitext="On May 5, 2021, Jane patted the cat after lunch."),
        previous_payload=previous_state,
        current_payload=current_state,
    )

    assert report["state_delta_summary"]["changed_anchor_event_ids"]
    assert report["graph_impact_summary"]["timeline"]["changed_anchor_event_ids"]
    assert any(packet["anchor_status_changed"] for packet in report["issue_packets"])


def test_revision_harness_cli_writes_report(tmp_path: Path) -> None:
    previous_snapshot = tmp_path / "prev_snapshot.json"
    current_snapshot = tmp_path / "curr_snapshot.json"
    previous_state = tmp_path / "prev_state.json"
    current_state = tmp_path / "curr_state.json"
    out_path = tmp_path / "report.json"

    previous_snapshot_obj = _snapshot(title="Example", revid=1, wikitext="Alpha beta")
    current_snapshot_obj = _snapshot(title="Example", revid=2, wikitext="Alpha gamma")
    previous_snapshot.write_text(json.dumps(previous_snapshot_obj), encoding="utf-8")
    current_snapshot.write_text(json.dumps(current_snapshot_obj), encoding="utf-8")
    previous_state.write_text(json.dumps(build_wiki_article_state(previous_snapshot_obj, no_spacy=True)), encoding="utf-8")
    current_state.write_text(json.dumps(build_wiki_article_state(current_snapshot_obj, no_spacy=True)), encoding="utf-8")

    completed = subprocess.run(
        [
            "python",
            "scripts/wiki_revision_harness.py",
            "--previous-snapshot",
            str(previous_snapshot),
            "--current-snapshot",
            str(current_snapshot),
            "--previous-state",
            str(previous_state),
            "--current-state",
            str(current_state),
            "--output",
            str(out_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )

    stdout = json.loads(completed.stdout)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["schema_version"] == "wiki_revision_harness_report_v0_1"
    assert file_payload["article"]["title"] == "Example"
