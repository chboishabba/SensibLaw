#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
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


def _coerce_arg_value(raw: str) -> str | Path | int | float:
    text = raw.strip()
    if not text:
        return text
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    for caster in (int, float):
        try:
            return caster(text)
        except ValueError:
            pass
    return Path(text) if "/" in text or text.endswith((".sqlite", ".db")) else text


def _extract_import_kwargs(lane: Any, args: argparse.Namespace) -> dict[str, object]:
    raw_kwargs: dict[str, object] = {}
    if args.storage_path is not None:
        raw_kwargs["storage_path"] = args.storage_path

    for item in args.lane_arg:
        if "=" not in item:
            raise ValueError(f"Invalid --lane-arg value '{item}'; expected key=value")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid --lane-arg value '{item}'; expected key=value")
        raw_kwargs[name] = _coerce_arg_value(value)

    signature = inspect.signature(lane.import_data)
    has_var_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )
    if has_var_kwargs:
        return raw_kwargs

    accepted = set(signature.parameters.keys())
    out: dict[str, object] = {}
    for key, value in raw_kwargs.items():
        if key in accepted:
            out[key] = value
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import lane-specific observation source rows into itir.sqlite.")
    parser.add_argument("--lane", required=True, help="Observation lane key, for example openrecall or worldmonitor")
    parser.add_argument("--source-path", type=Path, required=True, help="Source DB/file or directory for the lane")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Path to target ITIR SQLite DB")
    parser.add_argument(
        "--storage-path",
        type=Path,
        default=None,
        help="Optional lane-specific source storage override (for backward compatible OpenRecall compatibility)",
    )
    parser.add_argument(
        "--lane-arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Generic lane-specific import argument (repeatable).",
    )
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
    import_kwargs.update(_extract_import_kwargs(lane, args))

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
