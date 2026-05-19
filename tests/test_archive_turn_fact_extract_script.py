from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "archive_turn_fact_extract.py"
SPEC = importlib.util.spec_from_file_location("archive_turn_fact_extract", SCRIPT_PATH)
archive_turn_fact_extract = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(archive_turn_fact_extract)


def _seed_archive_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE messages (
              message_id TEXT PRIMARY KEY,
              canonical_thread_id TEXT,
              platform TEXT,
              account_id TEXT,
              ts TEXT,
              role TEXT,
              text TEXT,
              title TEXT,
              source_id TEXT,
              source_thread_id TEXT,
              source_message_id TEXT,
              source_path TEXT,
              source_bucket TEXT,
              provenance_json TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO messages (
              message_id, canonical_thread_id, platform, account_id, ts, role,
              text, title, source_id, source_thread_id, source_message_id,
              source_path, source_bucket, provenance_json
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    "msg-call",
                    "thread-1",
                    "chatgpt",
                    "acct",
                    "2026-01-14T23:45:15+00:00",
                    "user",
                    "What are our blockers? How can we move forwards?",
                    "Phase-4 Data Wait",
                    "src",
                    "source-thread",
                    "source-message-call",
                    "",
                    "",
                    "{}",
                ),
                (
                    "msg-response",
                    "thread-1",
                    "chatgpt",
                    "acct",
                    "2026-01-14T23:45:20+00:00",
                    "assistant",
                    (
                        "- configs/phase4_monitor_profiles.json now treats strict as canonical.\n"
                        "docs/phase4_density_monitor.md records waiting for density.\n"
                        "Phase-4.1 is blocked unless every strict-check bullet passes.\n"
                        "Please implement the notification routing feature by Friday.\n"
                        "Thanks."
                    ),
                    "Phase-4 Data Wait",
                    "src",
                    "source-thread",
                    "source-message-response",
                    "",
                    "",
                    "{}",
                ),
            ],
        )


def test_archive_turn_fact_extract_uses_existing_semantic_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "archive.sqlite"
    _seed_archive_db(db_path)

    turn = archive_turn_fact_extract.load_archive_turn(db_path, message_id="msg-call")
    payload = archive_turn_fact_extract.build_archive_turn_fact_extract(turn, run_id="archive-test-run")

    assert payload["schema_version"] == "sl.archive_turn_fact_extract.v0_1"
    assert payload["authority_boundary"]["uses_existing_sensiblaw_extractors"] is True
    assert payload["archive_turn"]["call"]["message_id"] == "msg-call"
    assert payload["archive_turn"]["response"]["message_id"] == "msg-response"
    assert len(payload["unit_debug"]) == 2

    call_debug = payload["unit_debug"][0]
    assert call_debug["sentence_split"][0]["text"] == "What are our blockers?"
    assert "interrogative" in call_debug["signal_summary"]["interaction"]

    response_debug = payload["unit_debug"][1]
    path_texts = {row["text"] for row in response_debug["file_path_occurrences"]}
    assert "configs/phase4_monitor_profiles.json" in path_texts
    assert "docs/phase4_density_monitor.md" in path_texts

    semantic_report = payload["semantic_report"]
    assert semantic_report["run_id"] == "archive-test-run"
    assert len(semantic_report["per_event"]) == 2
    assert semantic_report["summary"]["unresolved_mention_count"] >= 1

    relational_types = {row["type"] for row in response_debug["relational_bundle"]["relations"]}
    assert "predicate" in relational_types

    fact_payload = payload["fact_intake_payload"]
    assert fact_payload["run"]["contract_version"] == "fact.intake.bundle.v1"
    assert len(fact_payload["statements"]) == 2
