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

from src.reporting.openrecall_raw_import import (
    ensure_openrecall_raw_row_schema,
    import_openrecall_raw_rows,
    query_openrecall_raw_rows,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import raw OpenRecall rows into bounded SensibLaw staging tables."
    )
    parser.add_argument("--source-db", type=Path, required=True, help="Path to OpenRecall recall.db")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Target ITIR SQLite DB")
    parser.add_argument("--storage-path", type=Path, default=None, help="Optional OpenRecall storage root for screenshots")
    parser.add_argument("--limit", type=int, default=None, help="Optional max source rows to import")
    parser.add_argument("--import-run-id", default=None, help="Optional stable import run id")
    parser.add_argument("--show-rows", action="store_true", help="Include a small preview of imported raw rows")
    args = parser.parse_args(argv)

    import_run_id = args.import_run_id or f"openrecall-raw-import:{uuid.uuid4().hex[:12]}"
    args.itir_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(args.itir_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_raw_row_schema(conn)
        summary = import_openrecall_raw_rows(
            conn,
            source_db_path=args.source_db,
            import_run_id=import_run_id,
            storage_path=args.storage_path,
            limit=args.limit,
        )
        conn.commit()
        row_preview = (
            query_openrecall_raw_rows(conn, import_run_id=summary.import_run_id, limit=5)
            if args.show_rows
            else None
        )
    payload: dict[str, object] = {
        "ok": True,
        "importRunId": summary.import_run_id,
        "sourceDbPath": summary.source_db_path,
        "sourceEntryCount": summary.source_entry_count,
        "importedRowCount": summary.imported_row_count,
        "latestSourceTimestamp": summary.latest_source_timestamp,
        "itirDbPath": str(args.itir_db_path.resolve()),
    }
    if row_preview is not None:
        payload["rowPreview"] = row_preview
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
