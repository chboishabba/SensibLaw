from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TARGET_ONLINE_THREAD_ID = "69ac40e0-0cfc-839b-b2a8-0de3019379a9"
TARGET_TITLE_HINT = "Climate Change Politics AU"
CLAIM_HINTS = (
    "friendlyjordies",
    "greens",
    "cprs",
    "woolworths",
    "climate policy",
    "carbon pricing",
    "instant-runoff",
    "argued that",
    "said that",
    "reported that",
    "held that",
    "showed that",
)
CLAIM_CUE_PATTERN = re.compile(
    r"\b("
    r"said that|argued that|reported that|held that|showed that|"
    r"blocked|contributed to|delayed|uses|supports|passed|govern(?:s|ed)?|"
    r"woolworths|cprs|greens|friendlyjordies|climate policy|carbon pricing"
    r")\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True, slots=True)
class ArchiveMessage:
    role: str
    text: str
    ts: str
    thread_id: str
    title: str


def _db_candidates(repo_root: Path) -> list[Path]:
    return [
        Path.home() / ".chat_archive.sqlite",
        repo_root / ".chatgpt_history.sqlite3",
        repo_root / "chat-export-structurer" / "my_archive.sqlite",
    ]


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db_path.expanduser().resolve()}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA query_only=ON")
    return con


def _table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    return {str(row["name"]) for row in cur.execute(f"PRAGMA table_info({table})")}


def _rows_history_db(cur: sqlite3.Cursor) -> list[ArchiveMessage]:
    thread_id = TARGET_ONLINE_THREAD_ID
    title_hint = TARGET_TITLE_HINT.lower()
    target = cur.execute(
        """
        SELECT c.conversation_id AS thread_id, COALESCE(NULLIF(c.title, ''), '(untitled)') AS title
        FROM conversations c
        WHERE LOWER(c.conversation_id) = LOWER(?)
           OR LOWER(COALESCE(c.title, '')) LIKE ?
        ORDER BY CASE WHEN LOWER(c.conversation_id) = LOWER(?) THEN 0 ELSE 1 END,
                 c.last_seen_at DESC
        LIMIT 1
        """,
        (thread_id, f"%{title_hint}%", thread_id),
    ).fetchone()
    if target is None:
        return []

    rows = cur.execute(
        """
        SELECT m.author AS role, m.content AS text, COALESCE(CAST(m.create_time AS TEXT), '') AS ts
        FROM messages m
        WHERE LOWER(m.conversation_id) = LOWER(?)
        ORDER BY m.message_index ASC
        """,
        (target["thread_id"],),
    ).fetchall()
    return [
        ArchiveMessage(
            role=str(row["role"] or ""),
            text=str(row["text"] or ""),
            ts=str(row["ts"] or ""),
            thread_id=str(target["thread_id"]),
            title=str(target["title"] or "(untitled)"),
        )
        for row in rows
        if str(row["text"] or "").strip()
    ]


def _rows_archive_db(cur: sqlite3.Cursor, cols: set[str]) -> list[ArchiveMessage]:
    title_hint = TARGET_TITLE_HINT.lower()
    # Prefer exact source_thread_id or title; then keyword-density fallback.
    id_score_expr = "0"
    if "source_thread_id" in cols:
        id_score_expr = "SUM(CASE WHEN LOWER(COALESCE(source_thread_id, '')) = LOWER(?) THEN 100 ELSE 0 END)"

    title_score_expr = "0"
    if "title" in cols:
        title_score_expr = "SUM(CASE WHEN LOWER(COALESCE(title, '')) LIKE ? THEN 20 ELSE 0 END)"

    target = cur.execute(
        f"""
        WITH ranked AS (
          SELECT
            canonical_thread_id,
            COALESCE(NULLIF(MAX(COALESCE(title, '')), ''), '(untitled)') AS title,
            {id_score_expr} AS id_score,
            {title_score_expr} AS title_score,
            SUM(
              CASE WHEN LOWER(COALESCE(text, '')) LIKE '%friendlyjordies%' THEN 8 ELSE 0 END +
              CASE WHEN LOWER(COALESCE(text, '')) LIKE '%cprs%' THEN 6 ELSE 0 END +
              CASE WHEN LOWER(COALESCE(text, '')) LIKE '%greens%' THEN 3 ELSE 0 END +
              CASE WHEN LOWER(COALESCE(text, '')) LIKE '%woolworths%' THEN 3 ELSE 0 END +
              CASE WHEN LOWER(COALESCE(text, '')) LIKE '%climate policy%' THEN 3 ELSE 0 END +
              CASE WHEN LOWER(COALESCE(text, '')) LIKE '%carbon pricing%' THEN 3 ELSE 0 END
            ) AS keyword_score,
            MAX(ts) AS latest_ts
          FROM messages
          GROUP BY canonical_thread_id
        )
        SELECT canonical_thread_id, title
        FROM ranked
        ORDER BY (id_score + title_score + keyword_score) DESC, latest_ts DESC
        LIMIT 1
        """,
        tuple(
            value
            for cond, value in (
                ("source_thread_id" in cols, TARGET_ONLINE_THREAD_ID),
                ("title" in cols, f"%{title_hint}%"),
            )
            if cond
        ),
    ).fetchone()
    if target is None:
        return []

    rows = cur.execute(
        """
        SELECT role, text, COALESCE(ts, '') AS ts
        FROM messages
        WHERE canonical_thread_id = ?
        ORDER BY ts ASC, rowid ASC
        """,
        (target["canonical_thread_id"],),
    ).fetchall()
    return [
        ArchiveMessage(
            role=str(row["role"] or ""),
            text=str(row["text"] or ""),
            ts=str(row["ts"] or ""),
            thread_id=str(target["canonical_thread_id"]),
            title=str(target["title"] or "(untitled)"),
        )
        for row in rows
        if str(row["text"] or "").strip()
    ]


def _extract_claim_lines(messages: Iterable[ArchiveMessage], *, assistant: bool, limit: int) -> list[str]:
    def low_signal(text: str) -> bool:
        lowered = text.strip().lower()
        if not lowered:
            return True
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return True
        if re.fullmatch(r"[-=*#`>\s]+", lowered):
            return True
        if "subscribe/news" in lowered and "http" in lowered:
            return True
        return False

    out: list[str] = []
    for row in messages:
        role = row.role.strip().lower()
        is_assistant = role in {"assistant", "ai"}
        if assistant != is_assistant:
            continue
        for piece in SENTENCE_SPLIT.split(row.text):
            text = re.sub(r"\s+", " ", piece).strip()
            if len(text) < 20:
                continue
            if low_signal(text):
                continue
            if len(text) > 360:
                text = f"{text[:355].rstrip()}..."
            if CLAIM_CUE_PATTERN.search(text):
                out.append(text)
        if len(out) >= limit:
            break
    if out:
        return out[:limit]

    # Fallback: keep non-empty lines from the selected role so fixture is never empty.
    fallback: list[str] = []
    for row in messages:
        role = row.role.strip().lower()
        is_assistant = role in {"assistant", "ai"}
        if assistant != is_assistant:
            continue
        text = re.sub(r"\s+", " ", row.text).strip()
        if len(text) >= 20:
            if low_signal(text):
                continue
            fallback.append(text[:360] if len(text) > 360 else text)
        if len(fallback) >= limit:
            break
    return fallback[:limit]


def _unit_rows(source_id: str, lines: list[str]) -> list[dict[str, str]]:
    return [{"unit_id": f"{source_id}:u{idx}", "text": text} for idx, text in enumerate(lines, start=1)]


def _origin_url_for_thread(thread_id: str) -> str:
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        thread_id.lower(),
    ):
        return f"https://chatgpt.com/c/{thread_id}?src=history_search"
    return f"chat_archive://canonical_thread/{thread_id}"


def _build_thread_extract_payload(messages: list[ArchiveMessage]) -> dict:
    if not messages:
        return {}
    left_lines = _extract_claim_lines(messages, assistant=False, limit=12)
    right_lines = _extract_claim_lines(messages, assistant=True, limit=12)
    if not left_lines or not right_lines:
        return {}

    title = messages[0].title
    origin = _origin_url_for_thread(messages[0].thread_id)
    return {
        "fixture_id": "friendlyjordies_thread_extract_archive_v1",
        "label": "FriendlyJordies thread-derived extract (archive-backed)",
        "generated_from": {
            "thread_id": messages[0].thread_id,
            "thread_title": title,
            "message_count": len(messages),
            "keywords": list(CLAIM_HINTS),
        },
        "sources": [
            {
                "source_id": "jordies_thread_position",
                "title": f"Thread user-position extract: {title}",
                "origin_url": origin,
                "source_type": "analysis_transcript",
                "text_units": _unit_rows("jordies_thread_position", left_lines),
            },
            {
                "source_id": "thread_balanced_analysis",
                "title": f"Thread assistant-analysis extract: {title}",
                "origin_url": origin,
                "source_type": "analysis_transcript",
                "text_units": _unit_rows("thread_balanced_analysis", right_lines),
            },
        ],
    }


def _try_build_from_db(db_path: Path) -> dict:
    if not db_path.exists():
        return {}
    con = _connect_ro(db_path)
    try:
        cur = con.cursor()
        tables = {str(row["name"]) for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "messages" not in tables:
            return {}
        cols = _table_columns(cur, "messages")
        if {"conversation_id", "author", "content"}.issubset(cols) and "conversations" in tables:
            messages = _rows_history_db(cur)
        elif {"canonical_thread_id", "role", "text"}.issubset(cols):
            messages = _rows_archive_db(cur, cols)
        else:
            messages = []
        return _build_thread_extract_payload(messages)
    finally:
        con.close()


def build_archive_backed_fixture(
    *,
    fixture_name: str,
    repo_root: Path,
    output_dir: Path | None = None,
    db_paths: list[Path] | None = None,
) -> Path | None:
    if fixture_name != "friendlyjordies_thread_extract":
        return None
    candidates = db_paths or _db_candidates(repo_root)
    for db_path in candidates:
        payload = _try_build_from_db(db_path)
        if not payload:
            continue
        out_dir = output_dir or (repo_root / "SensibLaw" / ".cache_local" / "narrative")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{fixture_name}.archive.json"
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return out_path
    return None
