from __future__ import annotations

import json

from scripts.benchmark_fact_semantics import main


def test_benchmark_fact_semantics_script_smoke(tmp_path, capsys) -> None:
    db_path = tmp_path / "bench.sqlite"
    exit_code = main(["--mode", "chat_archive", "--count", "5", "--db-path", str(db_path)])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["mode"] == "chat_archive"
    assert payload["count"] == 5
    assert payload["elapsed_ms"] >= 0
    assert payload["refresh"]["refresh_status"] == "ok"
    assert "chat_archive" in payload["zelph"]["active_packs"]
    assert payload["persist_summary"]["semantic_assertion_count"] >= 1
