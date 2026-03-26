from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.build_personal_handoff_from_message_db import build_handoff_from_message_db_artifact, main


def _make_chat_db(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE chat_test_ingest_runs (
              run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              source_db_path TEXT NOT NULL,
              source_db_size INTEGER NOT NULL,
              sample_limit INTEGER NOT NULL,
              source_namespace TEXT NOT NULL,
              source_class TEXT NOT NULL,
              retention_policy TEXT NOT NULL,
              redaction_policy TEXT NOT NULL,
              backup_path TEXT,
              note TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE chat_test_messages (
              run_id TEXT NOT NULL,
              row_order INTEGER NOT NULL,
              thread_hash TEXT NOT NULL,
              platform TEXT NOT NULL,
              ts TEXT NOT NULL,
              role TEXT NOT NULL,
              text TEXT NOT NULL,
              PRIMARY KEY (run_id, row_order)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO chat_test_ingest_runs(
              run_id, created_at, source_db_path, source_db_size, sample_limit,
              source_namespace, source_class, retention_policy, redaction_policy,
              backup_path, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "chat-test:fixture",
                "2026-03-26T00:00:00Z",
                "/tmp/source.sqlite",
                123,
                2,
                "chat_test",
                "chat_archive_sample",
                "isolated_ephemeral_v1",
                "hashed_thread_only_v1",
                None,
                "fixture",
            ),
        )
        conn.executemany(
            """
            INSERT INTO chat_test_messages(run_id, row_order, thread_hash, platform, ts, role, text)
            VALUES (?,?,?,?,?,?,?)
            """,
            [
                ("chat-test:fixture", 1, "abc", "chatgpt", "2026-03-26T10:00:00Z", "user", "I wrote down the sequence after the appointment."),
                ("chat-test:fixture", 2, "abc", "chatgpt", "2026-03-26T10:01:00Z", "assistant", "Keep the chronology provisional until the letter arrives."),
            ],
        )
        conn.commit()


def _make_messenger_db(db_path: Path) -> None:
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
            INSERT INTO messenger_test_ingest_runs(
              run_id, created_at, source_db_path, source_db_size, sample_limit,
              source_namespace, source_class, retention_policy, redaction_policy, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "messenger-test:fixture",
                "2026-03-26T00:00:00Z",
                "/tmp/source.sqlite",
                123,
                2,
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
                ("messenger-test:fixture", 1, "abc", "one_to_one", "2026-03-26T10:00:00Z", "Alice", "I noted the sequence right after the meeting."),
                ("messenger-test:fixture", 2, "abc", "one_to_one", "2026-03-26T10:01:00Z", "Bob", "We should keep this within protected recipients."),
            ],
        )
        conn.commit()


def test_message_db_import_builds_personal_handoff_from_chat_db(tmp_path: Path) -> None:
    db_path = tmp_path / "chat.sqlite"
    _make_chat_db(db_path)

    payload = build_handoff_from_message_db_artifact(
        db_path=db_path,
        source_kind="chat",
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:chat_db_import",
        mode="personal_handoff",
        run_id="chat-test:fixture",
    )

    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert normalized["entries"][0]["text"] == "I wrote down the sequence after the appointment."
    assert report["recipient_export"]["exported_item_count"] == 2


def test_message_db_import_builds_protected_envelope_from_messenger_db(tmp_path: Path) -> None:
    db_path = tmp_path / "messenger.sqlite"
    _make_messenger_db(db_path)

    payload = build_handoff_from_message_db_artifact(
        db_path=db_path,
        source_kind="messenger",
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:messenger_db_import",
        mode="protected_disclosure_envelope",
        run_id="messenger-test:fixture",
    )

    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    serialized = json.dumps(report, sort_keys=True)
    assert normalized["entries"][0]["local_handle"] == "messenger_test_db://messenger-test:fixture:1"
    assert report["integrity"]["sealed_item_count"] == 2
    assert "I noted the sequence right after the meeting." not in serialized


def test_message_db_import_script_writes_artifact(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "chat.sqlite"
    _make_chat_db(db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--source-kind",
            "chat",
            "--recipient-profile",
            "lawyer",
            "--source-label",
            "fixture:chat_db_import",
            "--run-id",
            "chat-test:fixture",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["source_kind"] == "chat"
    assert Path(payload["report_path"]).exists()
