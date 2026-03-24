#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.qg_unification import as_trace_vector, build_dependency_span_payload


def _default_payload() -> dict:
    return {
        "da51": "trace-demo-001",
        "exponents": [1, 0, -1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "hot": 3,
        "cold": 7,
        "mass": 8,
        "steps": 42,
        "basin": 1,
        "j_fixed": False,
    }


def _serialize_datetime_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_payload(
    trace_vector: Any,
    envelope: Mapping[str, Any],
    *,
    run_id: str,
    source: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_time_utc": _serialize_datetime_now(),
        "contract": "DA51 (empirical) -> SL (canonical structure) -> Agda (formal proof)",
        "source": source,
        "trace_vector": {
            "id": trace_vector.id,
            "exponents": trace_vector.exponents,
            "normalized": trace_vector.normalized,
            "mass": trace_vector.mass,
            "sparsity": trace_vector.sparsity,
            "hot": trace_vector.hot,
            "cold": trace_vector.cold,
            "steps": trace_vector.steps,
            "basin": trace_vector.basin,
            "j_fixed": trace_vector.j_fixed,
            "mdls": trace_vector.mdls,
            "admissible": trace_vector.admissible,
        },
        "envelope": envelope,
    }


def _write_artifact(payload: Mapping[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"qg_unification_run_{payload['run_id']}.json"
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return file_path


def _ensure_db_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qg_unification_runs (
            run_id TEXT PRIMARY KEY,
            run_time_utc TEXT NOT NULL,
            contract TEXT NOT NULL,
            source TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            trace_vector_json TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _persist_to_db(record: Mapping[str, Any], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_db_schema(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO qg_unification_runs (
                run_id,
                run_time_utc,
                contract,
                source,
                artifact_path,
                trace_vector_json,
                envelope_json,
                payload_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["run_id"],
                record["run_time_utc"],
                record["contract"],
                record["source"],
                record["artifact_path"],
                json.dumps(record["trace_vector"], sort_keys=True),
                json.dumps(record["envelope"], sort_keys=True),
                json.dumps(record, sort_keys=True),
                _serialize_datetime_now(),
            ),
        )
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and persist a QG unification boundary artifact.")
    parser.add_argument(
        "--json",
        default=None,
        help="JSON object representing DA51Trace payload",
    )
    parser.add_argument("--json-file", type=Path, default=None, help="Path to JSON file containing DA51Trace payload")
    parser.add_argument("--out-dir", default=".cache_local/qg_unification_artifacts", help="Directory for emitted artifacts")
    parser.add_argument("--db-path", default="", help="Optional SQLite path for tracking persisted runs")
    parser.add_argument("--run-id", default="", help="Optional run identifier override")
    parser.add_argument("--source", default="da51", help="Source label for the staged adapter bridge")
    args = parser.parse_args(argv)

    payload = _default_payload()
    if args.json_file is not None:
        payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    elif args.json is not None:
        try:
            payload = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    {
                        "error": "invalid_json",
                        "detail": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2

    try:
        trace_vector = as_trace_vector(payload)
    except Exception as exc:  # pragma: no cover
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "invalid_payload": payload,
                    "kind": "validation_failed",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    envelope = build_dependency_span_payload(trace_vector)
    run_id = args.run_id.strip() or str(uuid.uuid4())
    out_dir = Path(args.out_dir)
    record = _build_payload(trace_vector, envelope, run_id=run_id, source=args.source)
    artifact_path = _write_artifact(record, out_dir)
    record["artifact_path"] = str(artifact_path)
    db_path = Path(args.db_path).expanduser() if args.db_path else None
    if db_path is not None:
        _persist_to_db(record, db_path)

    output = {
        "run_id": run_id,
        "artifact_path": str(artifact_path),
        "status": "persisted",
        "db_persisted": bool(db_path is not None),
    }
    if db_path is not None:
        output["db_path"] = str(db_path)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
