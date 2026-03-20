from __future__ import annotations

import json

from scripts.run_fact_semantic_benchmark_matrix import main


def test_run_fact_semantic_benchmark_matrix_script_smoke(tmp_path, capsys) -> None:
    baseline_dir = tmp_path / "baseline"
    output_dir = tmp_path / "reports"
    baseline_dir.mkdir()
    (baseline_dir / "chat_archive_100.json").write_text(
        json.dumps(
            {
                "corpus_id": "chat_archive",
                "count": 100,
                "elapsed_ms": 1000.0,
                "refresh": {
                    "assertion_count": 520,
                    "relation_count": 0,
                    "policy_count": 300,
                    "facts_serialized_count": 2380,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    exit_code = main(
        [
            "--manifest",
            "tests/fixtures/fact_semantic_bench/corpus_manifest.json",
            "--output-dir",
            str(output_dir),
            "--baseline-dir",
            str(baseline_dir),
            "--corpus-id",
            "chat_archive",
            "--max-tier",
            "100",
        ]
    )
    output = capsys.readouterr().out
    lines = [line for line in output.splitlines() if line.strip()]
    assert exit_code == 0
    assert any(line.startswith("[bench-matrix]") for line in lines)
    json_start = output.rfind("\n{")
    assert json_start != -1
    summary = json.loads(output[json_start + 1 :])
    assert summary["run_count"] == 1
    report_path = output_dir / next(path.name for path in output_dir.iterdir())
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["corpus_id"] == "chat_archive"
    assert payload["refresh"]["refresh_status"] == "ok"
    assert payload["baseline_report_path"].endswith("chat_archive_100.json")
    assert payload["drift"]["assertions"]["baseline"] == 520
    assert "assertion_count" in payload["guardrail_status"]
    assert payload["review_recommendations"]
