from __future__ import annotations

import json

from scripts.run_fact_semantic_benchmark_matrix import main


def test_run_fact_semantic_benchmark_matrix_script_smoke(tmp_path, capsys) -> None:
    output_dir = tmp_path / "reports"
    exit_code = main(
        [
            "--manifest",
            "tests/fixtures/fact_semantic_bench/corpus_manifest.json",
            "--output-dir",
            str(output_dir),
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
