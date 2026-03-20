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


def test_benchmark_fact_semantics_script_supports_corpus_file(tmp_path, capsys) -> None:
    db_path = tmp_path / "bench-corpus.sqlite"
    corpus_path = "tests/fixtures/fact_semantic_bench/wiki_revision_seed.json"
    exit_code = main(["--corpus-file", corpus_path, "--count", "6", "--db-path", str(db_path)])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["corpus_file"].endswith("wiki_revision_seed.json")
    assert payload["count"] == 6
    assert payload["corpus_summary"]["long_entry_count"] >= 1
    assert "wiki_article" in payload["corpus_summary"]["source_types"]
    assert payload["entry_diagnostics"]
    assert payload["expectation_summary"]["entry_count"] == 6
    assert payload["expectation_summary"]["class_expectation_recall"] >= 0.0
    assert payload["refresh"]["refresh_status"] == "ok"


def test_benchmark_fact_semantics_script_groups_repeated_entries(tmp_path, capsys) -> None:
    db_path = tmp_path / "bench-repeated.sqlite"
    corpus_path = "tests/fixtures/fact_semantic_bench/chat_archive_seed.json"
    exit_code = main(["--corpus-file", corpus_path, "--count", "20", "--db-path", str(db_path)])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    diagnostics = payload["entry_diagnostics"]
    assert len(diagnostics) == 10
    assert any(row["entry_id"] == "chat-adversarial-prompt-injection" for row in diagnostics)
    assert all(row["occurrence_count"] == 2 for row in diagnostics)
    assert payload["expectation_summary"]["entry_count"] == 10
