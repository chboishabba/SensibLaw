#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _serialize_datetime_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qg_unification_runs (
            run_id TEXT PRIMARY KEY,
            run_time_utc TEXT NOT NULL,
            contract TEXT NOT NULL,
            source TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            trace_vector_json TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _load_bridge_row(conn: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = conn.execute(
        "SELECT run_id, run_time_utc, contract, source, artifact_path, trace_vector_json, envelope_json, payload_json FROM qg_unification_runs WHERE run_id = ?",
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


def _coerce_record(raw: dict[str, object]) -> tuple[str, str, str, str, str, str, str, str, str]:
    payload_text = raw.get("payload_json")
    if not isinstance(payload_text, str):
        raise ValueError("payload_json is not a string in bridge row")

    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("payload_json must be an object")

    trace_vector = payload.get("trace_vector")
    envelope = payload.get("envelope")
    if not isinstance(trace_vector, dict):
        raise ValueError("payload trace_vector missing or invalid")
    if not isinstance(envelope, dict):
        raise ValueError("payload envelope missing or invalid")

    trace_id = str(trace_vector.get("id", ""))
    if not trace_id:
        raise ValueError("trace_vector.id missing")

    artifact_path = raw.get("artifact_path")
    if not isinstance(artifact_path, str):
        artifact_path = ""

    return (
        str(raw["run_id"]),
        str(raw["run_time_utc"]),
        str(raw["contract"]),
        str(raw["source"]),
        trace_id,
        artifact_path,
        json.dumps(trace_vector, sort_keys=True),
        json.dumps(envelope, sort_keys=True),
        json.dumps(payload, sort_keys=True),
    )


def _upsert_itir_run(conn: sqlite3.Connection, record: tuple[str, str, str, str, str, str, str, str, str]) -> None:
    run_id, run_time_utc, contract, source, trace_id, artifact_path, trace_vector_json, envelope_json, payload_json = record
    conn.execute(
        """
        INSERT OR REPLACE INTO qg_unification_runs (
            run_id,
            run_time_utc,
            contract,
            source,
            trace_id,
            artifact_path,
            trace_vector_json,
            envelope_json,
            payload_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            run_time_utc,
            contract,
            source,
            trace_id,
            artifact_path,
            trace_vector_json,
            envelope_json,
            payload_json,
            _serialize_datetime_now(),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consume a staged QG unification run into an ITIR-facing DB.")
    parser.add_argument("--run-id", required=True, help="Run identifier in bridge database")
    parser.add_argument(
        "--bridge-db",
        default=".cache_local/qg_unification_artifacts/qg_unification.sqlite",
        help="SQLite DB written by qg_unification_stage2_bridge.py",
    )
    parser.add_argument("--itir-db", required=True, help="Destination SQLite DB (ITIR/SL read-model)")
    parser.add_argument(
        "--require-artifact",
        action="store_true",
        help="Fail if the staged artifact file is missing for the selected run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Resolve and validate run, but do not write ITIR DB")
    args = parser.parse_args(argv)

    bridge_db = Path(args.bridge_db).expanduser()
    itir_db = Path(args.itir_db).expanduser()

    if not bridge_db.exists():
        print(
            json.dumps(
                {
                    "error": "bridge_db_not_found",
                    "bridge_db": str(bridge_db),
                    "run_id": args.run_id,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    if not args.dry_run and not itir_db.exists():
        print(
            json.dumps(
                {
                    "error": "itir_db_not_found",
                    "itir_db": str(itir_db),
                    "run_id": args.run_id,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    try:
        with sqlite3.connect(bridge_db) as bridge_conn:
            bridge_conn.row_factory = sqlite3.Row
            bridge_row = _load_bridge_row(bridge_conn, args.run_id)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "run_id": args.run_id,
                    "bridge_db": str(bridge_db),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    artifact_path = str(bridge_row.get("artifact_path") or "")
    if args.require_artifact:
        if not artifact_path:
            print(
                json.dumps(
                    {
                        "error": "artifact_path_missing",
                        "run_id": args.run_id,
                        "bridge_db": str(bridge_db),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        if not Path(artifact_path).exists():
            print(
                json.dumps(
                    {
                        "error": "artifact_not_found",
                        "run_id": args.run_id,
                        "artifact_path": artifact_path,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2

    try:
        record = _coerce_record(bridge_row)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "run_id": args.run_id,
                    "bridge_db": str(bridge_db),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    output = {
        "run_id": args.run_id,
        "status": "ready",
        "artifact_path": artifact_path,
        "trace_id": record[4],
    }

    if args.dry_run:
        output["dry_run"] = True
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0

    try:
        with sqlite3.connect(itir_db) as itir_conn:
            _ensure_schema(itir_conn)
            _upsert_itir_run(itir_conn, record)
            itir_conn.commit()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "run_id": args.run_id,
                    "itir_db": str(itir_db),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    output.update({"status": "persisted", "itir_db": str(itir_db)})
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
