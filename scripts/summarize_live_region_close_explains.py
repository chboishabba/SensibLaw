#!/usr/bin/env python3
"""Summarize genuine in-run region-close EXPLAIN records and verify commit state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pnf.numeric_hyperfabric import ClosureState, WorkState  # noqa: E402
from src.storage.postgres.spacy_parser_model import connect  # noqa: E402


def _load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"line {line_no} is not a JSON object")
        records.append(value)
    return records


def _commit_state(database_url: str, *, region_id: int, work_id: int) -> dict[str, Any]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT region.closure_state,
                           region.graph_revision,
                           region.closed_at,
                           work.state_id,
                           work.completed_at
                      FROM execution.semantic_pnf_region AS region
                      JOIN execution.semantic_pnf_work_item AS work
                        ON work.region_id = region.region_id
                     WHERE region.region_id = %s
                       AND work.work_id = %s
                    """,
                    (int(region_id), int(work_id)),
                )
                row = cursor.fetchone()
                if row is None:
                    return {"state": "missing"}
                closure_state = int(row[0])
                work_state = int(row[3])
                return {
                    "state": "observed",
                    "closure_state": closure_state,
                    "graph_revision": int(row[1]),
                    "closed_at": None if row[2] is None else str(row[2]),
                    "work_state": work_state,
                    "completed_at": None if row[4] is None else str(row[4]),
                    "commit_confirmed": (
                        closure_state == int(ClosureState.LOCALLY_CLOSED)
                        and work_state == int(WorkState.COMPLETED)
                    ),
                }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--database-url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    records = _load_records(args.input)
    configured: list[int] = []
    if records:
        configured = [
            int(value)
            for value in records[0].get("selection", {}).get("configured_ordinals", [])
        ]
    observed = [
        int(record.get("selection", {}).get("close_ordinal", 0)) for record in records
    ]
    summaries: list[dict[str, Any]] = []
    for record in records:
        preclose = record.get("preclose", {})
        support = record.get("semantic_support_vector")
        summary = {
            "close_ordinal": int(record.get("selection", {}).get("close_ordinal", 0)),
            "region_id": preclose.get("region_id"),
            "work_id": preclose.get("work_id"),
            "region_kind": preclose.get("region_kind"),
            "start_char": preclose.get("start_char"),
            "end_char": preclose.get("end_char"),
            "semantic_support_vector": support,
            "metrics": record.get("metrics", {}),
            "trigger_names": [
                trigger.get("trigger_name") for trigger in record.get("triggers", [])
            ],
            "capture_commit_confirmation": record.get("commit_confirmation", "unknown"),
        }
        if isinstance(support, dict):
            summary["support_axes"] = {
                "local_boundary_support": support.get("adjacent_candidate_side_count"),
                "local_anaphor_support": support.get("local_pronoun_token_count"),
                "document_regions": support.get("document_region_count"),
                "document_interfaces": support.get("document_interface_count"),
                "document_region_anchored_demands": support.get(
                    "document_region_anchored_demand_count"
                ),
                "document_mentions": support.get("document_mention_count"),
            }
        else:
            summary["support_axes"] = None
        if args.database_url and preclose.get("region_id") and preclose.get("work_id"):
            summary["post_run_commit_state"] = _commit_state(
                args.database_url,
                region_id=int(preclose["region_id"]),
                work_id=int(preclose["work_id"]),
            )
        else:
            summary["post_run_commit_state"] = {"state": "not_checked"}
        summaries.append(summary)

    missing = sorted(set(configured) - set(observed))
    report = {
        "contract_ref": "sensiblaw.live-region-close-explain-summary.v0_2",
        "input": str(args.input),
        "configured_ordinals": configured,
        "observed_ordinals": observed,
        "missing_ordinals": missing,
        "record_count": len(records),
        "support_vector_record_count": sum(
            1
            for record in records
            if isinstance(record.get("semantic_support_vector"), dict)
        ),
        "support_semantics": (
            "close ordinal is a selector only; compare trigger time against local "
            "fibre/boundary support separately from accumulated document populations"
        ),
        "records": summaries,
    }
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")
    return 0 if records and not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
