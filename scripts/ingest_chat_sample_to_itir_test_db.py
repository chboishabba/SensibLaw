#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.expanduser().resolve()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_test_ingest_runs (
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
        CREATE TABLE IF NOT EXISTS chat_test_messages (
          run_id TEXT NOT NULL,
          row_order INTEGER NOT NULL,
          thread_hash TEXT NOT NULL,
          platform TEXT NOT NULL,
          ts TEXT NOT NULL,
          role TEXT NOT NULL,
          text TEXT NOT NULL,
          PRIMARY KEY (run_id, row_order),
          FOREIGN KEY (run_id) REFERENCES chat_test_ingest_runs(run_id)
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_test_ingest_runs)").fetchall()}
    for name, decl in (
        ("source_namespace", "TEXT NOT NULL DEFAULT 'chat_test'"),
        ("source_class", "TEXT NOT NULL DEFAULT 'chat_archive_sample'"),
        ("retention_policy", "TEXT NOT NULL DEFAULT 'isolated_ephemeral_v1'"),
        ("redaction_policy", "TEXT NOT NULL DEFAULT 'hashed_thread_only_v1'"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE chat_test_ingest_runs ADD COLUMN {name} {decl}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_test_structural_atoms (
          atom_id INTEGER PRIMARY KEY,
          norm_text TEXT NOT NULL,
          norm_kind TEXT NOT NULL,
          UNIQUE (norm_text, norm_kind)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_test_structural_atom_occurrences (
          run_id TEXT NOT NULL,
          row_order INTEGER NOT NULL,
          occ_id INTEGER NOT NULL,
          atom_id INTEGER NOT NULL,
          start_char INTEGER NOT NULL,
          end_char INTEGER NOT NULL,
          token_index INTEGER,
          PRIMARY KEY (run_id, row_order, occ_id),
          FOREIGN KEY (run_id, row_order) REFERENCES chat_test_messages(run_id, row_order),
          FOREIGN KEY (atom_id) REFERENCES chat_test_structural_atoms(atom_id)
        )
        """
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _backup_live_db(live_db: Path) -> Path | None:
    if not live_db.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = live_db.with_name(f"{live_db.name}.bak-chat-sample-{stamp}")
    shutil.copy2(live_db, backup_path)
    return backup_path


def _persist_structural_atoms(dest_conn: sqlite3.Connection, run_id: str, row_order: int, text: str) -> None:
    sensiblaw_root = Path(__file__).resolve().parents[1]
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.sensiblaw.interfaces.shared_reducer import collect_canonical_structure_occurrences  # noqa: PLC0415

    occurrences = [
        occ
        for occ in collect_canonical_structure_occurrences(text, canonical_mode="deterministic_legal")
        if occ.kind.endswith("_ref")
    ]
    if not occurrences:
        return
    atom_keys = sorted({(occ.norm_text, occ.kind) for occ in occurrences})
    dest_conn.executemany(
        "INSERT OR IGNORE INTO chat_test_structural_atoms(norm_text, norm_kind) VALUES (?, ?)",
        atom_keys,
    )
    placeholders = ",".join("(?, ?)" for _ in atom_keys)
    flat: list[str] = []
    for norm_text, norm_kind in atom_keys:
        flat.extend([norm_text, norm_kind])
    rows = dest_conn.execute(
        f"SELECT atom_id, norm_text, norm_kind FROM chat_test_structural_atoms WHERE (norm_text, norm_kind) IN ({placeholders})",
        flat,
    ).fetchall()
    atom_ids = {(str(row["norm_text"]), str(row["norm_kind"])): int(row["atom_id"]) for row in rows}
    dest_conn.executemany(
        """
        INSERT INTO chat_test_structural_atom_occurrences(
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
    parser = argparse.ArgumentParser(description="Ingest a bounded local chat sample into an isolated ITIR test DB.")
    parser.add_argument("--source-db", default=str(Path("~/chat_archive.sqlite").expanduser()))
    parser.add_argument("--output-db", default=".cache_local/itir_chat_test.sqlite")
    parser.add_argument("--live-db", default=".cache_local/itir.sqlite")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--backup-live-db", action="store_true")
    parser.add_argument("--note", default="bounded chat sample for tokenizer/storage tests")
    parser.add_argument("--source-namespace", default="chat_test")
    parser.add_argument("--source-class", default="chat_archive_sample")
    parser.add_argument("--retention-policy", default="isolated_ephemeral_v1")
    parser.add_argument("--redaction-policy", default="hashed_thread_only_v1")
    args = parser.parse_args()

    source_db = Path(args.source_db).expanduser().resolve()
    output_db = Path(args.output_db).expanduser().resolve()
    live_db = Path(args.live_db).expanduser().resolve()
    output_db.parent.mkdir(parents=True, exist_ok=True)

    backup_path = _backup_live_db(live_db) if args.backup_live_db else None
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_id = "chat-test:" + _sha256_text(f"{source_db}:{created_at}:{args.limit}")[:16]

    with _connect_ro(source_db) as source_conn, sqlite3.connect(str(output_db)) as dest_conn:
        dest_conn.row_factory = sqlite3.Row
        _ensure_schema(dest_conn)
        rows = source_conn.execute(
            """
            SELECT canonical_thread_id, platform, ts, role, text
            FROM messages
            WHERE text IS NOT NULL AND TRIM(text) <> ''
            ORDER BY ts DESC, rowid DESC
            LIMIT ?
            """,
            (int(args.limit),),
        ).fetchall()
        dest_conn.execute(
            """
            INSERT OR REPLACE INTO chat_test_ingest_runs(
              run_id, created_at, source_db_path, source_db_size, sample_limit,
              source_namespace, source_class, retention_policy, redaction_policy,
              backup_path, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
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
                str(backup_path) if backup_path else None,
                str(args.note),
            ),
        )
        dest_conn.execute("DELETE FROM chat_test_messages WHERE run_id = ?", (run_id,))
        dest_conn.execute("DELETE FROM chat_test_structural_atom_occurrences WHERE run_id = ?", (run_id,))
        dest_conn.executemany(
            """
            INSERT INTO chat_test_messages(run_id, row_order, thread_hash, platform, ts, role, text)
            VALUES (?,?,?,?,?,?,?)
            """,
            [
                (
                    run_id,
                    index,
                    _sha256_text(str(row["canonical_thread_id"])),
                    str(row["platform"]),
                    str(row["ts"]),
                    str(row["role"]),
                    str(row["text"]),
                )
                for index, row in enumerate(rows, start=1)
            ],
        )
        for index, row in enumerate(rows, start=1):
            _persist_structural_atoms(dest_conn, run_id, index, str(row["text"]))
        dest_conn.commit()

    print(
        {
            "ok": True,
            "run_id": run_id,
            "source_db": str(source_db),
            "output_db": str(output_db),
            "backup_path": str(backup_path) if backup_path else None,
            "message_count": len(rows),
            "source_db_size": source_db.stat().st_size,
            "source_namespace": str(args.source_namespace),
            "retention_policy": str(args.retention_policy),
            "redaction_policy": str(args.redaction_policy),
        }
    )


if __name__ == "__main__":
    main()
