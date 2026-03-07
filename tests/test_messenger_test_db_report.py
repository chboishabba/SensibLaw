from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from SensibLaw.scripts.ingest_messenger_sample_to_itir_test_db import _classify_row, _split_sender_message_contamination


class _FakeRow(dict):
    pass


def test_messenger_row_classifier_filters_noise_deterministically():
    assert _classify_row(
        _FakeRow(sender="Facebook Marketplace Assistant", message="Your item has been listed", conversation="x", time_sent="2026-03-07T00:00:00Z")
    ) == "excluded_sender_or_conversation"
    assert _classify_row(
        _FakeRow(sender="Alice", message="Call started: 3 participants", conversation="x", time_sent="2026-03-07T00:00:00Z")
    ) == "system_fragment"
    assert _classify_row(
        _FakeRow(sender="Alice", message="ok", conversation="x", time_sent="2026-03-07T00:00:00Z")
    ) == "too_short"
    assert _classify_row(
        _FakeRow(sender="Alice", message="Here is the actual message body.", conversation="x", time_sent="2026-03-07T00:00:00Z")
    ) is None


def test_messenger_sender_message_contamination_is_split_deterministically():
    sender, message = _split_sender_message_contamination("FacebookWe didn’t remove the ad", "Thanks again for your report.")
    assert sender == "Facebook"
    assert message == "We didn’t remove the ad Thanks again for your report."

    sender, message = _split_sender_message_contamination("Chboi ShabbaWe received your report", "Thank you.")
    assert sender == "Chboi Shabba"
    assert message == "We received your report Thank you."


def test_messenger_report_script_outputs_filter_counts_and_structure(tmp_path: Path):
    db_path = tmp_path / "messenger.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE messenger_test_ingest_runs (
              run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              source_db_path TEXT NOT NULL,
              source_db_size INTEGER NOT NULL,
              sample_limit INTEGER NOT NULL,
              source_namespace TEXT NOT NULL,
              source_class TEXT NOT NULL,
              retention_policy TEXT NOT NULL,
              redaction_policy TEXT NOT NULL,
              note TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messenger_test_messages (
              run_id TEXT NOT NULL,
              row_order INTEGER NOT NULL,
              conversation_hash TEXT NOT NULL,
              conversation_type TEXT NOT NULL,
              ts TEXT NOT NULL,
              sender TEXT NOT NULL,
              text TEXT NOT NULL,
              PRIMARY KEY (run_id, row_order)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messenger_test_filter_stats (
              run_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              count INTEGER NOT NULL,
              PRIMARY KEY (run_id, reason)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO messenger_test_ingest_runs(
              run_id, created_at, source_db_path, source_db_size, sample_limit,
              source_namespace, source_class, retention_policy, redaction_policy, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "messenger-test:fixture",
                "2026-03-07T00:00:00Z",
                "/tmp/source.sqlite",
                123,
                10,
                "messenger_test",
                "facebook_messages_archive_sample",
                "isolated_ephemeral_v1",
                "conversation_hash_only_v1",
                "fixture",
            ),
        )
        conn.executemany(
            """
            INSERT INTO messenger_test_messages(run_id, row_order, conversation_hash, conversation_type, ts, sender, text)
            VALUES (?,?,?,?,?,?,?)
            """,
            [
                ("messenger-test:fixture", 1, "abc", "one_to_one", "2026-03-07T10:00:00Z", "Alice", "Check ./SensibLaw/tests/test_lexeme_layer.py"),
                ("messenger-test:fixture", 2, "abc", "one_to_one", "2026-03-07T10:01:00Z", "Bob", "Use --json please"),
            ],
        )
        conn.executemany(
            "INSERT INTO messenger_test_filter_stats(run_id, reason, count) VALUES (?,?,?)",
            [
                ("messenger-test:fixture", "system_fragment", 3),
                ("messenger-test:fixture", "too_short", 2),
            ],
        )
        conn.commit()

    script = Path(__file__).resolve().parents[1] / "scripts" / "report_messenger_test_tokenizer_stats.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--db-path", str(db_path), "--run-id", "messenger-test:fixture", "--top-n", "5", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["run_id"] == "messenger-test:fixture"
    assert payload["message_count"] == 2
    assert payload["filter_counts"] == {"system_fragment": 3, "too_short": 2}
    top_atoms = {(row["norm_text"], row["kind"]) for row in payload["top_structural_atoms"]}
    assert ("path:sensiblaw_tests_test_lexeme_layer_py", "path_ref") in top_atoms
    assert ("flag:--json", "flag_ref") in top_atoms
