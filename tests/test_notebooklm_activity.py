from __future__ import annotations

import json
from pathlib import Path

from src.reporting.notebooklm_activity import (
    build_notebooklm_activity_report,
    list_notebooklm_activity_dates,
    load_notebooklm_activity_units,
    query_notebooklm_activity_events,
)


def _seed_runs_root(tmp_path: Path) -> Path:
    runs_root = tmp_path / "runs"
    out_dir = runs_root / "2026-03-11" / "outputs" / "notebooklm"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ts": "2026-03-11T01:00:00Z",
            "signal": "notebooklm_activity",
            "app": "notebooklm",
            "event": "conversation_observed",
            "notebook_id_hash": "sha256:notebook123",
            "notebook_title": "Policy Notebook",
            "conversation_id_hash": "sha256:conv456",
            "query_preview": "What changed in the vendor plan?",
            "answer_preview": "The staged cutover now includes rollback checks.",
            "conversation_turn_ts": "2026-03-11T00:59:00Z",
            "provenance": {"source": "notebooklm_activity"},
        },
        {
            "ts": "2026-03-11T01:05:00Z",
            "signal": "notebooklm_activity",
            "app": "notebooklm",
            "event": "note_observed",
            "notebook_id_hash": "sha256:notebook123",
            "notebook_title": "Policy Notebook",
            "note_id_hash": "sha256:note789",
            "note_title": "Follow-up tasks",
            "note_preview": "Confirm the rollback window and owner handoff.",
            "note_length": 45,
            "provenance": {"source": "notebooklm_activity"},
        },
    ]
    target = out_dir / "notebooklm_activity_normalized.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return runs_root


def test_notebooklm_activity_report_summarizes_conversations_notes_and_dates(tmp_path: Path) -> None:
    runs_root = _seed_runs_root(tmp_path)
    report = build_notebooklm_activity_report(runs_root)
    assert report["summary"]["eventCount"] == 2
    assert report["summary"]["conversationCount"] == 1
    assert report["summary"]["noteCount"] == 1
    assert report["summary"]["eventCounts"]["conversation_observed"] == 1
    assert report["notebooks"][0]["title"] == "Policy Notebook"


def test_notebooklm_activity_dates_and_query_filtering_are_bounded(tmp_path: Path) -> None:
    runs_root = _seed_runs_root(tmp_path)
    dates = list_notebooklm_activity_dates(runs_root)
    assert dates == [
        {
            "date": "2026-03-11",
            "eventCount": 2,
            "notebookCount": 1,
            "conversationCount": 1,
            "noteCount": 1,
            "firstTs": "2026-03-11T01:00:00Z",
            "lastTs": "2026-03-11T01:05:00Z",
        }
    ]
    events = query_notebooklm_activity_events(
        runs_root,
        event="note_observed",
        text_query="rollback",
        limit=5,
    )
    assert len(events) == 1
    assert events[0]["noteTitle"] == "Follow-up tasks"


def test_load_notebooklm_activity_units_projects_previews_into_text_units(tmp_path: Path) -> None:
    runs_root = _seed_runs_root(tmp_path)
    units = load_notebooklm_activity_units(runs_root, limit=10)
    assert len(units) == 2
    assert units[0].source_type == "notebooklm_activity_preview"
    assert "Policy Notebook" in units[0].text
