#!/usr/bin/env python3
"""Watch active work-conserving PostgreSQL lanes and aggregate backend CPU."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
from time import monotonic, sleep
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _require_psycopg() -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as error:
        raise RuntimeError(
            "persistence watcher requires psycopg[binary]>=3.1"
        ) from error
    return psycopg


def _proc_cpu_ticks(pid: int) -> int | None:
    path = Path(f"/proc/{pid}/stat")
    try:
        value = path.read_text(encoding="utf-8")
    except OSError:
        return None
    close = value.rfind(")")
    if close < 0:
        return None
    fields = value[close + 2 :].split()
    if len(fields) <= 12:
        return None
    return int(fields[11]) + int(fields[12])


def _human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            return f"{amount:.1f}{unit}"
        amount /= 1024.0
    raise AssertionError("unreachable")


def _fetch_active(connection: Any) -> Sequence[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT run.stage_ref,
                   run.document_ref,
                   run.family_ref,
                   run.state_ref,
                   run.worker_budget,
                   lane.lane_ref,
                   lane.partition_no,
                   lane.state_ref,
                   lane.backend_pid,
                   lane.row_count,
                   lane.byte_count,
                   lane.elapsed_ms,
                   activity.state,
                   activity.wait_event_type,
                   activity.wait_event,
                   EXTRACT(EPOCH FROM
                       (CURRENT_TIMESTAMP - activity.query_start))
            FROM execution.document_persistence_run AS run
            LEFT JOIN execution.document_persistence_lane AS lane
              ON lane.stage_ref = run.stage_ref
            LEFT JOIN pg_stat_activity AS activity
              ON activity.pid = lane.backend_pid
            WHERE run.state_ref IN ('staging', 'staged', 'publishing')
            ORDER BY run.started_at, lane.lane_ref, lane.partition_no
            """
        )
        return tuple(cursor.fetchall())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Show active persistence lanes, PostgreSQL backend PIDs, waits, "
            "and aggregate local backend CPU."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Sampling interval in seconds (default: 1.0)",
    )
    parser.add_argument("--once", action="store_true", help="Print one sample and exit")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Append samples rather than refreshing the terminal",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required")
    if args.interval <= 0:
        raise SystemExit("--interval must be positive")

    psycopg = _require_psycopg()
    ticks_per_second = int(os.sysconf("SC_CLK_TCK"))
    previous: dict[int, tuple[float, int]] = {}
    with psycopg.connect(args.database_url, autocommit=True) as connection:
        while True:
            now = monotonic()
            rows = _fetch_active(connection)
            pids = {
                int(row[8]) for row in rows if row[8] is not None and int(row[8]) > 0
            }
            cpu_by_pid: dict[int, float | None] = {}
            for pid in sorted(pids):
                ticks = _proc_cpu_ticks(pid)
                prior = previous.get(pid)
                if ticks is None or prior is None or now <= prior[0]:
                    cpu_by_pid[pid] = None
                else:
                    elapsed = now - prior[0]
                    cpu_by_pid[pid] = (
                        100.0 * (ticks - prior[1]) / ticks_per_second / elapsed
                    )
                if ticks is not None:
                    previous[pid] = (now, ticks)
            previous = {pid: sample for pid, sample in previous.items() if pid in pids}

            if not args.no_clear and not args.once:
                print("\033[2J\033[H", end="")
            print(
                "Work-conserving PostgreSQL persistence — "
                + datetime.now().astimezone().isoformat(timespec="seconds")
            )
            aggregate = sum(value for value in cpu_by_pid.values() if value is not None)
            measured = sum(value is not None for value in cpu_by_pid.values())
            capacity = max(1, os.cpu_count() or 1) * 100.0
            print(
                f"active backends={len(pids)}  measured={measured}  "
                f"aggregate backend CPU={aggregate:.1f}% / {capacity:.0f}% host"
            )
            if not rows:
                print("No active work-conserving persistence stages.")
            else:
                print(
                    "family/lane        part state       pid    cpu    rows   "
                    "bytes      pg-state/wait"
                )
                for row in rows:
                    family = str(row[2])
                    lane = str(row[5] or "-")
                    partition = "-" if row[6] is None else str(row[6])
                    lane_state = str(row[7] or row[3])
                    pid = int(row[8]) if row[8] is not None else 0
                    cpu = cpu_by_pid.get(pid)
                    cpu_text = "  n/a" if cpu is None else f"{cpu:5.1f}%"
                    count = int(row[9] or 0)
                    byte_count = _human_bytes(int(row[10] or 0))
                    pg_state = str(row[12] or "detached")
                    wait = "/".join(str(value) for value in row[13:15] if value)
                    state_wait = pg_state if not wait else f"{pg_state}:{wait}"
                    print(
                        f"{family[:14]:14}/{lane[:8]:8} "
                        f"{partition:>4} {lane_state[:11]:11} "
                        f"{pid:>6} {cpu_text:>7} {count:>7} "
                        f"{byte_count:>9}  {state_wait}"
                    )
            sys.stdout.flush()
            if args.once:
                return 0
            sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
