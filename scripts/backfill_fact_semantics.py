from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from src.fact_intake import list_fact_intake_runs, persist_fact_semantic_materialization


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill normalized fact semantics for persisted fact_intake runs.")
    parser.add_argument("--db-path", required=True, help="Path to the SensibLaw SQLite database.")
    parser.add_argument("--run-id", action="append", default=[], help="Specific fact_intake run_id to backfill. Repeatable.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit when no run_id is provided.")
    args = parser.parse_args(argv)

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        run_ids = list(args.run_id)
        if not run_ids:
            rows = list_fact_intake_runs(conn, limit=args.limit or 100000)
            run_ids = [str(row["run_id"]) for row in rows]
        def progress(update: dict[str, object]) -> None:
            print(
                f"[semantic-refresh] run={update['run_id']} status={update['status']} "
                f"stage={update['stage']} assertions={update['assertion_count']} "
                f"relations={update['relation_count']} policies={update['policy_count']} "
                f"msg={update['message']}"
            )
        payload = {
            "db_path": str(db_path),
            "run_count": len(run_ids),
            "runs": [
                persist_fact_semantic_materialization(
                    conn,
                    run_id=run_id,
                    include_zelph=True,
                    refresh_kind="backfill",
                    progress_callback=progress,
                )
                for run_id in run_ids
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
