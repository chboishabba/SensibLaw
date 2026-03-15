from __future__ import annotations

import json
from pathlib import Path

from scripts.transcript_fact_review import main


def test_transcript_fact_review_script_bundle_emits_review_bundle(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    transcript_path = tmp_path / "hearing_transcript.txt"
    transcript_path.write_text(
        "Q: Where were you?\n\nA: At home.\n\n[5/3/26 8:52 pm] Alice: Thanks.\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--transcript-file",
            str(transcript_path),
            "--known-participants",
            f"{transcript_path.resolve()}=counsel,witness",
            "bundle",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["version"] == "fact.review.bundle.v1"
    assert payload["run"]["workflow_link"]["workflow_kind"] == "transcript_semantic"
    assert payload["summary"]["fact_count"] == 3
    assert payload["summary"]["event_count"] >= 1
    assert "operator_views" in payload
    assert any(row["event_type"] == "communication" for row in payload["events"])


def test_transcript_fact_review_script_run_emits_summary_ids(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    transcript_path = tmp_path / "hearing_transcript.txt"
    transcript_path.write_text(
        "Q: Where were you?\n\nA: At home.\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--transcript-file",
            str(transcript_path),
            "--run-id",
            "transcript-fact-script-v1",
            "run",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["semanticRunId"] == "transcript-fact-script-v1"
    assert payload["factRunId"].startswith("factrun:")
    assert payload["workflowLink"]["workflow_kind"] == "transcript_semantic"
    assert payload["reopenQuery"]["workflowKind"] == "transcript_semantic"
    assert payload["latestSourceQuery"]["workflowKind"] == "transcript_semantic"
    assert payload["factPersist"]["statement_count"] == 2
    assert payload["bundleSummary"]["fact_count"] == 2
