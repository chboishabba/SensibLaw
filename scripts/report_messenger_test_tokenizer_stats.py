#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _load_messenger_units(db_path: Path, run_id: str | None) -> tuple[str | None, list]:
    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.reporting.structure_report import load_messenger_units  # noqa: PLC0415

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if run_id is None:
            row = conn.execute(
                "SELECT run_id FROM messenger_test_ingest_runs ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None, []
            run_id = str(row["run_id"])
        return run_id, load_messenger_units(db_path, run_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report tokenizer/compression + structure stats for the isolated Messenger test DB.")
    parser.add_argument("--db-path", default=".cache_local/itir_messenger_test.sqlite")
    parser.add_argument("--run-id")
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.reporting.structure_report import build_structure_report  # noqa: PLC0415

    db_path = Path(args.db_path).expanduser().resolve()
    resolved_run_id, units = _load_messenger_units(db_path, args.run_id)
    report = build_structure_report(units, top_n=args.top_n)

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        run_row = None
        filter_rows = []
        if resolved_run_id is not None:
            run_row = conn.execute(
                """
                SELECT source_namespace, source_class, retention_policy, redaction_policy, sample_limit
                FROM messenger_test_ingest_runs
                WHERE run_id = ?
                """,
                (resolved_run_id,),
            ).fetchone()
            has_filter_stats = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'messenger_test_filter_stats'"
            ).fetchone()
            if has_filter_stats is not None:
                filter_rows = conn.execute(
                    """
                    SELECT reason, count
                    FROM messenger_test_filter_stats
                    WHERE run_id = ?
                    ORDER BY count DESC, reason ASC
                    """,
                    (resolved_run_id,),
                ).fetchall()

    payload = {
        "db_path": str(db_path),
        "run_id": resolved_run_id,
        "message_count": report["unit_count"],
        "filter_counts": {str(row["reason"]): int(row["count"]) for row in filter_rows},
        "source_namespace": None if run_row is None else str(run_row["source_namespace"]),
        "source_class": None if run_row is None else str(run_row["source_class"]),
        "retention_policy": None if run_row is None else str(run_row["retention_policy"]),
        "redaction_policy": None if run_row is None else str(run_row["redaction_policy"]),
        "sample_limit": None if run_row is None else int(run_row["sample_limit"]),
        **report,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
