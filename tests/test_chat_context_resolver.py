from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts/chat_context_resolver.py"
_SPEC = importlib.util.spec_from_file_location("chat_context_resolver", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
_query_db_match = _MODULE._query_db_match


def _init_messages_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE messages (
          message_id TEXT PRIMARY KEY,
          canonical_thread_id TEXT NOT NULL,
          platform TEXT NOT NULL,
          account_id TEXT NOT NULL,
          ts TEXT NOT NULL,
          role TEXT NOT NULL,
          text TEXT NOT NULL,
          title TEXT,
          source_id TEXT NOT NULL,
          source_thread_id TEXT,
          source_message_id TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO messages(
          message_id, canonical_thread_id, platform, account_id, ts, role, text, title, source_id, source_thread_id, source_message_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "m1",
            "canon-123",
            "chatgpt",
            "main",
            "2026-03-07T05:29:37+00:00",
            "assistant",
            "latest body",
            "Wikidata Ontology Issues",
            "pull_20260307T053644Z",
            "699dd5af-d65c-83a0-80ae-fda8e4d66f5b",
            "msg-1",
        ),
    )
    conn.commit()
    conn.close()


def test_query_db_match_prefers_online_thread_id_exact(tmp_path: Path) -> None:
    db_path = tmp_path / "archive.sqlite"
    _init_messages_db(db_path)

    match = _query_db_match(db_path, "699dd5af-d65c-83a0-80ae-fda8e4d66f5b")

    assert match is not None
    assert match.match_type == "online_thread_id_exact"
    assert match.online_thread_id == "699dd5af-d65c-83a0-80ae-fda8e4d66f5b"
    assert match.canonical_thread_id == "canon-123"
    assert match.title == "Wikidata Ontology Issues"
