from __future__ import annotations

import json
from pathlib import Path

from scripts.report_wiki_random_timeline_readiness import (
    build_timeline_readiness_report,
    main,
    score_snapshot_payload,
)


def _write_snapshot(tmp_path: Path, *, name: str, title: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "wiki": "enwiki",
                "title": title,
                "pageid": 1,
                "revid": 100,
                "source_url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "wikitext": text,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_score_snapshot_payload_reports_timeline_and_aao_readiness() -> None:
    row = score_snapshot_payload(
        {
            "title": "Timeline example",
            "wikitext": (
                "== Early life ==\n"
                "On May 5, 2021, Dr Smith performed surgery on the plaintiff.\n"
                "In June 2021, the court ordered damages."
            ),
        },
        no_spacy=True,
    )

    assert row["timeline_candidate_count"] >= 1
    assert row["aao_event_count"] >= 1
    assert row["dated_timeline_candidate_count"] >= 1
    assert row["scores"]["candidate_retention_score"] > 0.0
    assert row["scores"]["chronology_support_score"] > 0.0


def test_build_timeline_readiness_report_aggregates_pages(tmp_path: Path) -> None:
    strong_path = _write_snapshot(
        tmp_path,
        name="strong.json",
        title="Strong example",
        text=(
            "== Campaign ==\n"
            "On May 5, 2021, Dr Smith performed surgery on the plaintiff.\n"
            "In June 2021, the court ordered damages."
        ),
    )
    weak_path = _write_snapshot(
        tmp_path,
        name="weak.json",
        title="Weak example",
        text="This article describes a musician and an album release with sparse chronology.",
    )
    manifest = {
        "generated_at": "2026-03-15T00:00:00Z",
        "wiki": "enwiki",
        "requested_count": 2,
        "sampled_count": 2,
        "namespace": 0,
        "samples": [
            {"snapshot_path": str(strong_path)},
            {"snapshot_path": str(weak_path)},
        ],
    }

    report = build_timeline_readiness_report(manifest, emit_page_rows=True, no_spacy=True)
    assert report["schema_version"] == "wiki_random_timeline_readiness_report_v0_1"
    assert report["summary"]["page_count"] == 2
    assert report["summary"]["pages_with_timeline_candidates"] >= 1
    assert report["summary"]["pages_with_aao_events"] >= 1
    assert len(report["pages"]) == 2


def test_timeline_readiness_main_writes_report(tmp_path: Path, capsys) -> None:
    snapshot_path = _write_snapshot(
        tmp_path,
        name="timeline.json",
        title="Timeline example",
        text=(
            "== Early life ==\n"
            "On May 5, 2021, Dr Smith performed surgery on the plaintiff.\n"
            "In June 2021, the court ordered damages."
        ),
    )
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-15T00:00:00Z",
                "wiki": "enwiki",
                "requested_count": 1,
                "sampled_count": 1,
                "namespace": 0,
                "samples": [{"snapshot_path": str(snapshot_path)}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--manifest",
            str(manifest_path),
            "--output",
            str(report_path),
            "--emit-page-rows",
            "--no-spacy",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report_path.exists()
    assert payload["summary"]["page_count"] == 1
    assert payload["pages"][0]["title"] == "Timeline example"
