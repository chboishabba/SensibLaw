from __future__ import annotations

import json
from pathlib import Path

from scripts.report_wiki_random_lexer_coverage import build_coverage_report, main, score_snapshot_payload


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


def test_score_snapshot_payload_distinguishes_structural_signal_from_plain_text() -> None:
    legal = score_snapshot_payload(
        {
            "title": "Legal example",
            "wikitext": "Civil Liability Act 2002 (NSW) s 5B applies in the High Court of Australia.",
        }
    )
    plain = score_snapshot_payload(
        {
            "title": "Plain example",
            "wikitext": "This article is about a musician and a football match with no legal references.",
        }
    )

    assert legal["structural_token_count"] > 0
    assert legal["scores"]["structural_coverage_score"] > 0.0
    assert plain["scores"]["abstention_quality_score"] == 1.0
    assert "no_structural_signal" in plain["issues"]


def test_build_coverage_report_aggregates_page_rows(tmp_path: Path) -> None:
    legal_path = _write_snapshot(
        tmp_path,
        name="legal.json",
        title="Legal example",
        text="Civil Liability Act 2002 (NSW) s 5B applies in the High Court of Australia.",
    )
    plain_path = _write_snapshot(
        tmp_path,
        name="plain.json",
        title="Plain example",
        text="This article is about a musician and a football match with no legal references.",
    )
    manifest = {
        "generated_at": "2026-03-15T00:00:00Z",
        "wiki": "enwiki",
        "requested_count": 2,
        "sampled_count": 2,
        "namespace": 0,
        "samples": [
            {"snapshot_path": str(legal_path)},
            {"snapshot_path": str(plain_path)},
        ],
    }

    report = build_coverage_report(manifest, emit_page_rows=True)
    assert report["schema_version"] == "wiki_random_lexer_coverage_report_v0_1"
    assert report["summary"]["page_count"] == 2
    assert report["summary"]["pages_with_structural_signal"] >= 1
    assert report["summary"]["pages_with_no_signal"] >= 1
    assert report["supported_surface"]["shared_reducer_surface"] == "scored"
    assert len(report["pages"]) == 2


def test_coverage_main_writes_report(tmp_path: Path, capsys) -> None:
    legal_path = _write_snapshot(
        tmp_path,
        name="legal.json",
        title="Legal example",
        text="Civil Liability Act 2002 (NSW) s 5B applies in the High Court of Australia.",
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
                "samples": [{"snapshot_path": str(legal_path)}],
            }
        ),
        encoding="utf-8",
    )
    exit_code = main(["--manifest", str(manifest_path), "--output", str(report_path), "--emit-page-rows"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report_path.exists()
    assert payload["summary"]["page_count"] == 1
    assert payload["pages"][0]["title"] == "Legal example"
