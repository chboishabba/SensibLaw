from __future__ import annotations

import json
from pathlib import Path

from src.reporting.notebooklm_observer import (
    MAX_QUERY_ROWS,
    build_bounded_notebooklm_observer_report,
    build_notebooklm_observer_report,
    list_notebooklm_observer_dates,
    load_notebooklm_units,
    query_notebooklm_observer_artifacts,
    query_notebooklm_observer_dates,
    query_notebooklm_observer_events,
    query_notebooklm_observer_notebooks,
    query_notebooklm_observer_sources,
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


def test_notebooklm_observer_report_summarizes_dates_notebooks_sources_and_artifacts(
    tmp_path: Path,
) -> None:
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


def test_notebooklm_observer_dates_and_event_query_are_bounded_and_filterable(
    tmp_path: Path,
) -> None:
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


def test_load_notebooklm_units_projects_source_summaries_into_text_units(
    tmp_path: Path,
) -> None:
    runs_root = _seed_runs_root(tmp_path)
    units = load_notebooklm_units(runs_root, limit=10)
    assert len(units) == 1
    assert units[0].source_type == "notebooklm_source_summary"
    assert "[Notebook] Policy Notebook" in units[0].text
    assert "[Source] Vendor transition notes" in units[0].text
    assert "staged cutover" in units[0].text.casefold()



def test_notebooklm_bounded_entity_queries_filter_canonical_report(
    tmp_path: Path,
) -> None:
    runs_root = _seed_runs_root(tmp_path)

    notebooks = query_notebooklm_observer_notebooks(
        runs_root,
        text_query="policy",
        limit=9999,
    )
    assert [row["notebookIdHash"] for row in notebooks] == ["sha256:notebook123"]

    sources = query_notebooklm_observer_sources(
        runs_root,
        source_type="sourceType.google_docs",
        source_status="READY",
        text_query="rollback",
        limit=9999,
    )
    assert [row["noteIdHash"] for row in sources] == ["sha256:source456"]

    artifacts = query_notebooklm_observer_artifacts(
        runs_root,
        artifact_type="REPORT",
        artifact_status="ready",
        text_query="executive",
        limit=9999,
    )
    assert [row["artifactIdHash"] for row in artifacts] == ["sha256:artifact789"]


def test_notebooklm_bounded_report_and_date_query_publish_effective_caps(
    tmp_path: Path,
) -> None:
    runs_root = _seed_runs_root(tmp_path)

    dates = query_notebooklm_observer_dates(runs_root, limit=9999)
    assert [row["date"] for row in dates] == ["2026-02-11"]

    report = build_bounded_notebooklm_observer_report(
        runs_root,
        event_limit=9999,
        entity_limit=9999,
    )
    assert report["bounds"] == {
        "entityLimit": MAX_QUERY_ROWS,
        "eventLimit": MAX_QUERY_ROWS,
        "maxQueryRows": MAX_QUERY_ROWS,
    }
    assert report["summary"]["eventCount"] == 4
    assert len(report["recentEvents"]) == 4
    assert len(report["notebooks"]) == 1
    assert len(report["sources"]) == 1
    assert len(report["artifacts"]) == 1
