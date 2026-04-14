#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import uuid

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.reporting.worldmonitor_import import ensure_worldmonitor_capture_schema, import_worldmonitor_data, load_worldmonitor_units


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import WorldMonitor JSON captures into itir.sqlite as observer-class artifacts.")
    parser.add_argument("--source-path", type=Path, required=True, help="Path to WorldMonitor export JSON or directory")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Target ITIR SQLite DB")
    parser.add_argument("--limit", type=int, default=None, help="Optional max source files")
    parser.add_argument("--import-run-id", default=None, help="Optional stable import run id")
    parser.add_argument("--show-units", action="store_true", help="Include a small preview of imported text units")
    args = parser.parse_args(argv)

    import_run_id = args.import_run_id or f"worldmonitor-import:{uuid.uuid4().hex[:12]}"
    args.itir_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(args.itir_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_worldmonitor_capture_schema(conn)
        summary = import_worldmonitor_data(
            conn,
            source_path=args.source_path,
            import_run_id=import_run_id,
            limit=args.limit,
        )
        conn.commit()

    payload: dict[str, object] = {
        "ok": True,
        "importRunId": summary.import_run_id,
        "sourcePath": summary.source_path,
        "sourceFileCount": summary.source_file_count,
        "sourceRecordCount": summary.source_record_count,
        "importedCaptureCount": summary.imported_capture_count,
        "latestSourceTimestamp": summary.latest_source_timestamp,
        "itirDbPath": str(args.itir_db_path.resolve()),
    }
    if args.show_units:
        units = load_worldmonitor_units(args.itir_db_path, import_run_id=summary.import_run_id, limit=5)
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
