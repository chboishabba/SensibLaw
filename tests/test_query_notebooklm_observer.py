from __future__ import annotations

import json
from pathlib import Path

from scripts.query_notebooklm_observer import main


def _seed_runs_root(tmp_path: Path) -> Path:
    runs_root = tmp_path / "runs"
    notes_dir = runs_root / "2026-03-11" / "logs" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ts": "2026-03-11T10:00:00Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "notebook_observed",
            "notebook_id_hash": "sha256:notebook-a",
            "notebook_title": "Policy Notebook",
            "provenance": {"source": "notebooklm_meta"},
        },
        {
            "ts": "2026-03-11T10:01:00Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "source_observed",
            "notebook_id_hash": "sha256:notebook-a",
            "notebook_title": "Policy Notebook",
            "note_id_hash": "sha256:source-a",
            "source_title": "Transition memo",
            "source_type": "SourceType.GOOGLE_DOCS",
            "source_status": "ready",
            "source_summary": "Rollback window and staged cutover.",
            "source_keywords": ["rollback", "cutover"],
            "provenance": {"source": "notebooklm_meta"},
        },
        {
            "ts": "2026-03-11T10:02:00Z",
            "signal": "notes_meta",
            "app": "notebooklm",
            "event": "artifact_observed",
            "notebook_id_hash": "sha256:notebook-a",
            "artifact_id_hash": "sha256:artifact-a",
            "artifact_title": "Executive Brief",
            "artifact_type": "report",
            "artifact_status": "ready",
            "provenance": {"source": "notebooklm_meta"},
        },
    ]
    target = notes_dir / "2026-03-11.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return runs_root


def test_query_notebooklm_observer_cli_exposes_bounded_entity_queries(
    tmp_path: Path,
    capsys,
) -> None:
    runs_root = _seed_runs_root(tmp_path)

    assert main(
        [
            "--runs-root",
            str(runs_root),
            "sources",
            "--source-type",
            "sourcetype.google_docs",
            "--source-status",
            "READY",
            "--text-query",
            "rollback",
            "--limit",
            "9999",
        ]
    ) == 0
    sources_payload = json.loads(capsys.readouterr().out)
    assert [row["noteIdHash"] for row in sources_payload["sources"]] == [
        "sha256:source-a"
    ]

    assert main(
        [
            "--runs-root",
            str(runs_root),
            "artifacts",
            "--artifact-type",
            "REPORT",
            "--artifact-status",
            "ready",
            "--text-query",
            "executive",
        ]
    ) == 0
    artifacts_payload = json.loads(capsys.readouterr().out)
    assert [row["artifactIdHash"] for row in artifacts_payload["artifacts"]] == [
        "sha256:artifact-a"
    ]


def test_query_notebooklm_observer_cli_summary_reports_effective_bounds(
    tmp_path: Path,
    capsys,
) -> None:
    runs_root = _seed_runs_root(tmp_path)

    assert main(
        [
            "--runs-root",
            str(runs_root),
            "summary",
            "--event-limit",
            "9999",
            "--entity-limit",
            "9999",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    report = payload["report"]
    assert report["bounds"] == {
        "entityLimit": 500,
        "eventLimit": 500,
        "maxQueryRows": 500,
    }
    assert report["summary"]["eventCount"] == 3
    assert len(report["notebooks"]) == 1
    assert len(report["sources"]) == 1
    assert len(report["artifacts"]) == 1


def test_query_notebooklm_observer_cli_dates_and_notebooks_are_bounded(
    tmp_path: Path,
    capsys,
) -> None:
    runs_root = _seed_runs_root(tmp_path)

    assert main(["--runs-root", str(runs_root), "dates", "--limit", "1"]) == 0
    dates_payload = json.loads(capsys.readouterr().out)
    assert [row["date"] for row in dates_payload["dates"]] == ["2026-03-11"]

    assert main(
        [
            "--runs-root",
            str(runs_root),
            "notebooks",
            "--text-query",
            "policy",
            "--limit",
            "1",
        ]
    ) == 0
    notebooks_payload = json.loads(capsys.readouterr().out)
    assert [row["notebookIdHash"] for row in notebooks_payload["notebooks"]] == [
        "sha256:notebook-a"
    ]
