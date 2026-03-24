#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _serialize_datetime_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_utterance_text(trace_vector: dict[str, Any]) -> str:
    trace_id = str(trace_vector.get("id") or "")
    mass = trace_vector.get("mass", 0)
    steps = trace_vector.get("steps", 0)
    hot = trace_vector.get("hot", 0)
    cold = trace_vector.get("cold", 0)
    basin = trace_vector.get("basin", 0)
    admissible = str(trace_vector.get("admissible", False)).lower()
    return (
        f"QG unification capture for trace {trace_id}: "
        f"mass={mass}, steps={steps}, hot={hot}, cold={cold}, basin={basin}, "
        f"admissible={admissible}."
    )


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qg_tirc_capture_runs (
            run_id TEXT PRIMARY KEY,
            bridge_run_id TEXT NOT NULL,
            source TEXT NOT NULL,
            contract TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            run_time_utc TEXT NOT NULL,
            trace_vector_json TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qg_tirc_capture_sessions (
            session_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            connector TEXT NOT NULL DEFAULT 'qg_unification',
            session_started_at TEXT NOT NULL,
            session_ended_at TEXT NOT NULL,
            origin TEXT NOT NULL,
            audio_sha256 TEXT NOT NULL,
            source_doc_hash TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES qg_tirc_capture_runs(run_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qg_tirc_capture_utterances (
            utterance_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            speaker_label TEXT NOT NULL,
            speaker_confidence REAL NOT NULL DEFAULT 1.0,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            text TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES qg_tirc_capture_sessions(session_id) ON DELETE CASCADE
        )
        """
    )


def _read_bridge_row(conn: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = conn.execute(
        """
        SELECT run_id, run_time_utc, contract, source, artifact_path,
               trace_vector_json, envelope_json, payload_json
        FROM qg_unification_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"run_id not found in bridge db: {run_id}")
    return {
        "run_id": row[0],
        "run_time_utc": row[1],
        "contract": row[2],
        "source": row[3],
        "artifact_path": row[4],
        "trace_vector_json": row[5],
        "envelope_json": row[6],
        "payload_json": row[7],
    }


def _coerce_payload(raw: dict[str, object]) -> dict[str, Any]:
    if not isinstance(raw.get("payload_json"), str):
        raise ValueError("payload_json missing or not a JSON string")
    payload = json.loads(str(raw["payload_json"]))
    if not isinstance(payload, dict):
        raise ValueError("payload_json is not an object")
    trace_vector = payload.get("trace_vector")
    if not isinstance(trace_vector, dict):
        raise ValueError("payload trace_vector missing or invalid")
    if not str(trace_vector.get("id", "")).strip():
        raise ValueError("trace_vector.id missing")
    raw_run_time = str(raw.get("run_time_utc") or "").strip()
    if not raw_run_time:
        raw_run_time = _serialize_datetime_now()
    return {
        "run_id": str(raw["run_id"]),
        "run_time_utc": raw_run_time.replace("Z", "+00:00"),
        "contract": str(raw["contract"]),
        "source": str(raw["source"]),
        "artifact_path": str(raw["artifact_path"]),
        "trace_vector_json": str(raw["trace_vector_json"]),
        "envelope_json": str(raw["envelope_json"]),
        "payload_json": str(raw["payload_json"]),
        "trace_vector": trace_vector,
    }


def _upsert_rows(
    conn: sqlite3.Connection,
    data: dict[str, Any],
    *,
    session_id: str,
) -> tuple[str, str]:
    run_id = data["run_id"]
    started_at = datetime.fromisoformat(data["run_time_utc"])
    ended_at = started_at + timedelta(seconds=max(1, int(data["trace_vector"].get("steps", 1))))
    utterance_text = _build_utterance_text(data["trace_vector"])
    utterance_hash = hashlib.sha256(utterance_text.encode("utf-8")).hexdigest()

    conn.execute(
        """
        INSERT OR REPLACE INTO qg_tirc_capture_runs(
            run_id, bridge_run_id, source, contract, trace_id, artifact_path,
            run_time_utc, trace_vector_json, envelope_json, payload_json, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            run_id,
            data["source"],
            data["contract"],
            str(data["trace_vector"]["id"]),
            data["artifact_path"],
            data["run_time_utc"],
            data["trace_vector_json"],
            data["envelope_json"],
            data["payload_json"],
            _serialize_datetime_now(),
        ),
    )
    conn.execute("DELETE FROM qg_tirc_capture_sessions WHERE run_id = ?", (run_id,))
    conn.execute(
        """
        INSERT INTO qg_tirc_capture_sessions(
            session_id, run_id, connector, session_started_at, session_ended_at,
            origin, audio_sha256, source_doc_hash
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            session_id,
            run_id,
            "qg_unification",
            started_at.isoformat(timespec="seconds"),
            ended_at.isoformat(timespec="seconds"),
            "qg_unification_bridge",
            hashlib.sha256(run_id.encode("utf-8")).hexdigest(),
            hashlib.sha1(json.dumps(data["trace_vector"], sort_keys=True).encode("utf-8")).hexdigest(),
        ),
    )
    utterance_id = f"{session_id}:utt-1"
    conn.execute("DELETE FROM qg_tirc_capture_utterances WHERE session_id = ?", (session_id,))
    conn.execute(
        """
        INSERT INTO qg_tirc_capture_utterances(
            utterance_id, session_id, speaker_label, speaker_confidence,
            start_time, end_time, text, text_hash, raw_json
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            utterance_id,
            session_id,
            "QG_SENSOR",
            0.99,
            started_at.isoformat(timespec="seconds"),
            ended_at.isoformat(timespec="seconds"),
            utterance_text,
            utterance_hash,
            json.dumps(
                {
                    "run_id": run_id,
                    "contract": data["contract"],
                    "source": data["source"],
                    "envelope": json.loads(data["envelope_json"]),
                    "trace_vector": data["trace_vector"],
                },
                sort_keys=True,
            ),
        ),
    )
    return session_id, utterance_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist a QG run into a TiRC/transcript capture-style sink.")
    parser.add_argument("--run-id", required=True, help="Run identifier in bridge DB")
    parser.add_argument(
        "--bridge-db",
        default=".cache_local/qg_unification_artifacts/qg_unification.sqlite",
        help="SQLite DB written by qg_unification_stage2_bridge.py",
    )
    parser.add_argument("--itir-db", required=True, help="Destination SQLite DB")
    parser.add_argument("--session-id", default="", help="Optional deterministic session identifier override")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and validate run, but do not write ITIR DB")

    args = parser.parse_args(argv)
    bridge_db = Path(args.bridge_db).expanduser().resolve()
    itir_db = Path(args.itir_db).expanduser().resolve()

    if not bridge_db.exists():
        print(json.dumps({"error": "bridge_db_not_found", "bridge_db": str(bridge_db), "run_id": args.run_id}, indent=2, sort_keys=True))
        return 2
    if not itir_db.exists():
        print(json.dumps({"error": "itir_db_not_found", "itir_db": str(itir_db), "run_id": args.run_id}, indent=2, sort_keys=True))
        return 2

    try:
        with sqlite3.connect(bridge_db) as bridge_conn:
            row = _read_bridge_row(bridge_conn, args.run_id)
        payload = _coerce_payload(row)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "run_id": args.run_id, "bridge_db": str(bridge_db)}, indent=2, sort_keys=True))
        return 2

    session_id = args.session_id.strip() or f"qg-unification:{payload['run_id']}:capture-session"
    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "ready",
                    "run_id": payload["run_id"],
                    "session_id": session_id,
                    "utterance_count": 1,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        with sqlite3.connect(itir_db) as itir_conn:
            _ensure_schema(itir_conn)
            itir_conn.execute("PRAGMA foreign_keys = ON")
            _upsert_rows(itir_conn, payload, session_id=session_id)
            itir_conn.commit()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "run_id": payload["run_id"],
                    "itir_db": str(itir_db),
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": "persisted",
                "run_id": payload["run_id"],
                "session_id": session_id,
                "utterance_id": f"{session_id}:utt-1",
                "itir_db": str(itir_db),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
