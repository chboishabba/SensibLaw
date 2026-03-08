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
_build_stitched_transcript = _MODULE._build_stitched_transcript
_thread_analysis_payload = _MODULE._thread_analysis_payload
_cross_thread_analysis_payload = _MODULE._cross_thread_analysis_payload


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
    conn.execute(
        """
        INSERT INTO messages(
          message_id, canonical_thread_id, platform, account_id, ts, role, text, title, source_id, source_thread_id, source_message_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "m2",
            "canon-123",
            "chatgpt",
            "main",
            "2026-03-07T05:30:37+00:00",
            "user",
            "feature mention on first line\nsecond feature line",
            "Wikidata Ontology Issues",
            "pull_20260307T053644Z",
            "699dd5af-d65c-83a0-80ae-fda8e4d66f5b",
            "msg-2",
        ),
    )
    conn.execute(
        """
        INSERT INTO messages(
          message_id, canonical_thread_id, platform, account_id, ts, role, text, title, source_id, source_thread_id, source_message_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "m3",
            "canon-456",
            "chatgpt",
            "main",
            "2026-03-08T05:29:37+00:00",
            "assistant",
            "feature report feature workflow deadline feature",
            "Mission Feature Thread",
            "pull_20260308T053644Z",
            "799dd5af-d65c-83a0-80ae-fda8e4d66f5b",
            "msg-3",
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


def test_build_stitched_transcript_assigns_thread_and_message_line_numbers() -> None:
    transcript = _build_stitched_transcript(
        [
            {"message_id": "m1", "ts": "2026-03-07T05:29:37+00:00", "role": "assistant", "text": "alpha\nbeta"},
            {"message_id": "m2", "ts": "2026-03-07T05:30:37+00:00", "role": "user", "text": "gamma"},
        ]
    )

    assert [row.thread_line for row in transcript] == [1, 2, 3]
    assert [row.message_line for row in transcript] == [1, 2, 1]
    assert [row.message_index for row in transcript] == [1, 1, 2]


def test_thread_analysis_payload_reports_mentions_and_ranges(tmp_path: Path) -> None:
    db_path = tmp_path / "archive.sqlite"
    _init_messages_db(db_path)

    payload = _thread_analysis_payload(
        db_path,
        "canon-123",
        terms=["feature"],
        regex=False,
        case_sensitive=False,
        thread_range=(2, 3),
        message_range=None,
        show_lines=True,
        show_line_context=1,
        top_terms_limit=3,
        max_text_chars=0,
    )

    assert payload["analysis_scope"] == "thread_local"
    assert payload["transcript_stats"]["stitched_line_count"] == 2
    assert payload["term_stats"][0]["raw_count"] == 2
    assert payload["mentions"][0]["thread_line_start"] == 2
    assert payload["mentions"][0]["message_index"] == 2
    assert payload["lines"][0]["thread_line"] == 2
    assert payload["top_terms"]


def test_cross_thread_analysis_payload_ranks_threads_by_term_frequency(tmp_path: Path) -> None:
    db_path = tmp_path / "archive.sqlite"
    _init_messages_db(db_path)

    payload = _cross_thread_analysis_payload(
        db_path,
        "feature",
        terms=["feature"],
        regex=False,
        case_sensitive=False,
        limit=5,
        max_text_chars=0,
    )

    assert payload["analysis_scope"] == "cross_thread"
    assert payload["results"]
    assert payload["results"][0]["canonical_thread_id"] == "canon-456"
    assert payload["results"][0]["raw_count"] >= payload["results"][1]["raw_count"]
