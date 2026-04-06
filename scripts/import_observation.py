#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.reporting.observation_lanes import (
    get_observation_lane,
    load_observation_units,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import lane-specific observation source rows into itir.sqlite.")
    parser.add_argument("--lane", required=True, help="Observation lane key, for example openrecall or worldmonitor")
    parser.add_argument("--source-path", type=Path, required=True, help="Source DB/file or directory for the lane")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Path to target ITIR SQLite DB")
    parser.add_argument("--storage-path", type=Path, default=None, help="OpenRecall-only storage path override")
    parser.add_argument("--limit", type=int, default=None, help="Optional max source rows/files to import")
    parser.add_argument("--import-run-id", default=None, help="Optional stable import run id")
    parser.add_argument("--show-units", action="store_true", help="Include a small preview of imported text units")
    args = parser.parse_args(argv)

    lane = get_observation_lane(args.lane)
    if lane is None:
        raise ValueError(f"Unknown observation lane: {args.lane}")

    import_run_id = args.import_run_id or f"{lane.key}-import:{uuid.uuid4().hex[:12]}"
    args.itir_db_path.parent.mkdir(parents=True, exist_ok=True)

    import_kwargs: dict[str, Any] = {
        "source_path": str(args.source_path),
        "import_run_id": import_run_id,
        "limit": args.limit,
    }
    if args.storage_path is not None:
        import_kwargs["storage_path"] = args.storage_path

    with _connect(args.itir_db_path) as conn:
        lane.ensure_schema(conn)
        summary = lane.import_data(conn, **import_kwargs)
        conn.commit()

        payload: dict[str, object] = {
            "ok": True,
            "lane": lane.key,
            "importRunId": getattr(summary, "import_run_id", import_run_id),
            "sourcePath": str(args.source_path),
            "importedCaptureCount": getattr(summary, "imported_capture_count", None),
            "latestSourceTimestamp": getattr(summary, "latest_source_timestamp", None),
            "itirDbPath": str(args.itir_db_path.resolve()),
        }

        source_db_path = getattr(summary, "source_db_path", None)
        if source_db_path is not None:
            payload["sourceDbPath"] = str(source_db_path)
        source_file_count = getattr(summary, "source_file_count", None)
        if source_file_count is not None:
            payload["sourceFileCount"] = source_file_count
        source_record_count = getattr(summary, "source_record_count", None)
        if source_record_count is not None:
            payload["sourceRecordCount"] = source_record_count

        if args.show_units:
            units = load_observation_units(args.itir_db_path, lane.key, import_run_id=summary.import_run_id, limit=5)
            payload["unitPreview"] = [
                {
                    "unitId": unit.unit_id,
                    "sourceId": unit.source_id,
                    "sourceType": unit.source_type,
                    "text": unit.text[:160],
                }
                for unit in units
            ]

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
