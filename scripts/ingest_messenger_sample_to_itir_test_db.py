#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


SYSTEM_MESSAGE_FRAGMENTS = (
    "left the group.",
    "started this chat.",
    "sent an attachment.",
    "sent a photo.",
    "sent a video.",
    "sent a voice message.",
    "shared a post.",
    "shared a reel.",
    "named the group thread",
    "call started:",
    "call ended:",
    "call participants:",
    "reacted ",
    "device manufacturer",
    "device model",
    "device type",
    "ip address",
)
EXCLUDED_SENDERS = {
    "Unknown Sender",
    "Autofill information",
    "Messenger Contacts You've Blocked",
    "Facebook user",
    "Facebook Marketplace Assistant",
}
EXCLUDED_CONVERSATIONS = {
    "Messenger Contacts You've Blocked",
    "Your messages",
    "Autofill information",
}
EXCLUDED_SENDER_PREFIXES = (
    "a list of",
    "group invite link",
    "audio call",
    "you anonymously reported ",
    "marketplace",
)
MIN_MEANINGFUL_CHARS = 8


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.expanduser().resolve()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messenger_test_ingest_runs (
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
        CREATE TABLE IF NOT EXISTS messenger_test_filter_stats (
          run_id TEXT NOT NULL,
          reason TEXT NOT NULL,
          count INTEGER NOT NULL,
          PRIMARY KEY (run_id, reason),
          FOREIGN KEY (run_id) REFERENCES messenger_test_ingest_runs(run_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messenger_test_messages (
          run_id TEXT NOT NULL,
          row_order INTEGER NOT NULL,
          conversation_hash TEXT NOT NULL,
          conversation_type TEXT NOT NULL,
          ts TEXT NOT NULL,
          sender TEXT NOT NULL,
          text TEXT NOT NULL,
          PRIMARY KEY (run_id, row_order),
          FOREIGN KEY (run_id) REFERENCES messenger_test_ingest_runs(run_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messenger_test_structural_atoms (
          atom_id INTEGER PRIMARY KEY,
          norm_text TEXT NOT NULL,
          norm_kind TEXT NOT NULL,
          UNIQUE (norm_text, norm_kind)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messenger_test_structural_atom_occurrences (
          run_id TEXT NOT NULL,
          row_order INTEGER NOT NULL,
          occ_id INTEGER NOT NULL,
          atom_id INTEGER NOT NULL,
          start_char INTEGER NOT NULL,
          end_char INTEGER NOT NULL,
          token_index INTEGER,
          PRIMARY KEY (run_id, row_order, occ_id),
          FOREIGN KEY (run_id, row_order) REFERENCES messenger_test_messages(run_id, row_order),
          FOREIGN KEY (atom_id) REFERENCES messenger_test_structural_atoms(atom_id)
        )
        """
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _meaningful_char_count(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum())


def _classify_row(row: sqlite3.Row | dict[str, object]) -> str | None:
    sender = str(row["sender"] or "").strip()
    message = str(row["message"] or "").strip()
    conversation = str(row["conversation"] or "").strip()
    ts = str(row["time_sent"] or "").strip()
    if not sender or not message:
        return "missing_sender_or_message"
    if not ts:
        return "missing_timestamp"
    if sender in EXCLUDED_SENDERS or conversation in EXCLUDED_CONVERSATIONS:
        return "excluded_sender_or_conversation"
    sender_lowered = sender.casefold()
    if any(sender_lowered.startswith(prefix) for prefix in EXCLUDED_SENDER_PREFIXES):
        return "excluded_sender_prefix"
    lowered = message.casefold()
    if any(fragment in lowered for fragment in SYSTEM_MESSAGE_FRAGMENTS):
        return "system_fragment"
    if lowered.startswith(("you sent ", "you replied to ", "you unsent ", "you missed ", "you can now ")):
        return "system_prefix"
    if "marketplace" in lowered and "http" not in lowered and "https" not in lowered:
        return "marketplace_noise"
    if _meaningful_char_count(message) < MIN_MEANINGFUL_CHARS:
        return "too_short"
    return None


def _persist_structural_atoms(dest_conn: sqlite3.Connection, run_id: str, row_order: int, text: str) -> None:
    sensiblaw_root = Path(__file__).resolve().parents[1]
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.text.structure_index import collect_structure_occurrences  # noqa: PLC0415

    occurrences = [occ for occ in collect_structure_occurrences(text, canonical_mode="deterministic_legal") if occ.kind.endswith("_ref")]
    if not occurrences:
        return
    atom_keys = sorted({(occ.norm_text, occ.kind) for occ in occurrences})
    dest_conn.executemany(
        "INSERT OR IGNORE INTO messenger_test_structural_atoms(norm_text, norm_kind) VALUES (?, ?)",
        atom_keys,
    )
    placeholders = ",".join("(?, ?)" for _ in atom_keys)
    flat: list[str] = []
    for norm_text, norm_kind in atom_keys:
        flat.extend([norm_text, norm_kind])
    rows = dest_conn.execute(
        f"SELECT atom_id, norm_text, norm_kind FROM messenger_test_structural_atoms WHERE (norm_text, norm_kind) IN ({placeholders})",
        flat,
    ).fetchall()
    atom_ids = {(str(row["norm_text"]), str(row["norm_kind"])): int(row["atom_id"]) for row in rows}
    dest_conn.executemany(
        """
        INSERT INTO messenger_test_structural_atom_occurrences(
          run_id, row_order, occ_id, atom_id, start_char, end_char, token_index
        ) VALUES (?,?,?,?,?,?,?)
        """,
        [
            (
                run_id,
                row_order,
                index,
                atom_ids[(occ.norm_text, occ.kind)],
                occ.start_char,
                occ.end_char,
                index - 1,
            )
            for index, occ in enumerate(occurrences, start=1)
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a bounded Messenger/Facebook message sample into an isolated ITIR test DB.")
    parser.add_argument(
        "--source-db",
        default="/mnt/truenas/gem-net/Ubuntu 2025-11 (WORK TO DELETE ME OVER TIME PLS)/Documents/facebook_messages.db",
    )
    parser.add_argument("--output-db", default=".cache_local/itir_messenger_test.sqlite")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--note", default="bounded messenger sample for transcript/message structure tests")
    parser.add_argument("--source-namespace", default="messenger_test")
    parser.add_argument("--source-class", default="facebook_messages_archive_sample")
    parser.add_argument("--retention-policy", default="isolated_ephemeral_v1")
    parser.add_argument("--redaction-policy", default="conversation_hash_only_v1")
    args = parser.parse_args()

    source_db = Path(args.source_db).expanduser().resolve()
    output_db = Path(args.output_db).expanduser().resolve()
    output_db.parent.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_id = "messenger-test:" + _sha256_text(f"{source_db}:{created_at}:{args.limit}")[:16]

    with _connect_ro(source_db) as source_conn, sqlite3.connect(str(output_db)) as dest_conn:
        dest_conn.row_factory = sqlite3.Row
        _ensure_schema(dest_conn)
        rows = source_conn.execute(
            """
            SELECT message_id, time_sent, sender, message, conversation, conversation_type
            FROM messages
            WHERE message IS NOT NULL AND TRIM(message) <> ''
            ORDER BY time_sent DESC, message_id DESC
            LIMIT ?
            """,
            (int(args.limit) * 5,),
        ).fetchall()
        kept: list[sqlite3.Row] = []
        filter_counts: dict[str, int] = {}
        for row in rows:
            reason = _classify_row(row)
            if reason is None:
                kept.append(row)
                if len(kept) >= int(args.limit):
                    break
            else:
                filter_counts[reason] = filter_counts.get(reason, 0) + 1
        dest_conn.execute(
            """
            INSERT OR REPLACE INTO messenger_test_ingest_runs(
              run_id, created_at, source_db_path, source_db_size, sample_limit,
              source_namespace, source_class, retention_policy, redaction_policy, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                created_at,
                str(source_db),
                source_db.stat().st_size,
                int(args.limit),
                str(args.source_namespace),
                str(args.source_class),
                str(args.retention_policy),
                str(args.redaction_policy),
                str(args.note),
            ),
        )
        dest_conn.execute("DELETE FROM messenger_test_messages WHERE run_id = ?", (run_id,))
        dest_conn.execute("DELETE FROM messenger_test_structural_atom_occurrences WHERE run_id = ?", (run_id,))
        dest_conn.execute("DELETE FROM messenger_test_filter_stats WHERE run_id = ?", (run_id,))
        if filter_counts:
            dest_conn.executemany(
                "INSERT INTO messenger_test_filter_stats(run_id, reason, count) VALUES (?,?,?)",
                [(run_id, reason, count) for reason, count in sorted(filter_counts.items())],
            )
        payload_rows = []
        for index, row in enumerate(kept, start=1):
            ts = str(row["time_sent"] or "").strip()
            sender = str(row["sender"] or "").strip()
            message = str(row["message"] or "").strip()
            conversation = str(row["conversation"] or "").strip()
            payload_rows.append(
                (
                    run_id,
                    index,
                    _sha256_text(conversation),
                    str(row["conversation_type"] or ""),
                    ts,
                    sender,
                    message,
                )
            )
        dest_conn.executemany(
            """
            INSERT INTO messenger_test_messages(run_id, row_order, conversation_hash, conversation_type, ts, sender, text)
            VALUES (?,?,?,?,?,?,?)
            """,
            payload_rows,
        )
        for index, row in enumerate(kept, start=1):
            rendered = f"[{row['time_sent']}] {row['sender']}: {row['message']}"
            _persist_structural_atoms(dest_conn, run_id, index, rendered)
        dest_conn.commit()
    print(run_id)
    print(f"kept_rows={len(kept)}")
    print(f"filter_counts={filter_counts}")
    print(f"output_db={output_db}")


if __name__ == "__main__":
    main()
