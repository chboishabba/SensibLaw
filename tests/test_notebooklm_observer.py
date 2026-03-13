from __future__ import annotations

import json
from pathlib import Path

from src.reporting.notebooklm_observer import (
    build_notebooklm_observer_report,
    list_notebooklm_observer_dates,
    load_notebooklm_units,
    query_notebooklm_observer_events,
)


def _seed_runs_root(tmp_path: Path) -> Path:
    runs_root = tmp_path / "runs"
    notes_dir = runs_root / "2026-02-11" / "logs" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ts": "2026-02-11T05:41:42Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "context_observed",
            "has_context": False,
            "provenance": {"source": "notebooklm_meta"},
        },
        {
            "ts": "2026-02-11T05:41:42Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "notebook_observed",
            "notebook_id_hash": "sha256:notebook123",
            "notebook_title": "Policy Notebook",
            "provenance": {"source": "notebooklm_meta"},
        },
        {
            "ts": "2026-02-11T05:41:42Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "source_observed",
            "notebook_id_hash": "sha256:notebook123",
            "notebook_title": "Policy Notebook",
            "note_id_hash": "sha256:source456",
            "source_title": "Vendor transition notes",
            "source_type": "SourceType.GOOGLE_DOCS",
            "source_status": "ready",
            "source_url": "https://example.test/doc/123",
            "source_summary": "The vendor transition requires a staged cutover and a rollback window.",
            "source_keywords": ["vendor", "transition", "rollback"],
            "provenance": {"source": "notebooklm_meta"},
        },
        {
            "ts": "2026-02-11T05:45:00Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "artifact_observed",
            "notebook_id_hash": "sha256:notebook123",
            "artifact_id_hash": "sha256:artifact789",
            "artifact_title": "Executive Brief",
            "artifact_type": "report",
            "artifact_status": "ready",
            "artifact_created_at": "2026-02-11T05:44:58Z",
            "provenance": {"source": "notebooklm_meta"},
        },
    ]
    target = notes_dir / "2026-02-11.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return runs_root


def test_notebooklm_observer_report_summarizes_dates_notebooks_sources_and_artifacts(tmp_path: Path) -> None:
    runs_root = _seed_runs_root(tmp_path)
    report = build_notebooklm_observer_report(runs_root)
    assert report["summary"]["eventCount"] == 4
    assert report["summary"]["notebookCount"] == 1
    assert report["summary"]["sourceCount"] == 1
    assert report["summary"]["artifactCount"] == 1
    assert report["summary"]["sourceSummaryCount"] == 1
    assert report["summary"]["eventCounts"]["source_observed"] == 1
    assert report["notebooks"][0]["title"] == "Policy Notebook"
    assert report["sources"][0]["title"] == "Vendor transition notes"
    assert report["artifacts"][0]["title"] == "Executive Brief"


def test_notebooklm_observer_dates_and_event_query_are_bounded_and_filterable(tmp_path: Path) -> None:
    runs_root = _seed_runs_root(tmp_path)
    dates = list_notebooklm_observer_dates(runs_root)
    assert dates == [
        {
            "date": "2026-02-11",
            "eventCount": 4,
            "notebookCount": 1,
            "sourceCount": 1,
            "artifactCount": 1,
            "firstTs": "2026-02-11T05:41:42Z",
            "lastTs": "2026-02-11T05:45:00Z",
        }
    ]
    events = query_notebooklm_observer_events(
        runs_root,
        event="source_observed",
        text_query="rollback",
        limit=5,
    )
    assert len(events) == 1
    assert events[0]["sourceTitle"] == "Vendor transition notes"
    assert "rollback" in (events[0]["sourceSummary"] or "").casefold()


def test_load_notebooklm_units_projects_source_summaries_into_text_units(tmp_path: Path) -> None:
    runs_root = _seed_runs_root(tmp_path)
    units = load_notebooklm_units(runs_root, limit=10)
    assert len(units) == 1
    assert units[0].source_type == "notebooklm_source_summary"
    assert "[Notebook] Policy Notebook" in units[0].text
    assert "[Source] Vendor transition notes" in units[0].text
    assert "staged cutover" in units[0].text.casefold()
