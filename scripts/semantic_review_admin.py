#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="DB-backed semantic review admin helpers.")
    parser.add_argument("--db-path", default=".cache_local/itir.sqlite")
    sub = parser.add_subparsers(dest="cmd", required=True)

    list_p = sub.add_parser("list-corrections")
    list_p.add_argument("--source", required=True)
    list_p.add_argument("--run-id", default="")
    list_p.add_argument("--limit", type=int, default=24)

    submit_p = sub.add_parser("submit-correction")
    submit_p.add_argument("--payload-json", required=True)

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.gwb_us_law.semantic import (  # noqa: PLC0415
        ensure_gwb_semantic_schema,
        list_semantic_review_submissions,
        submit_semantic_review_submission,
    )

    with sqlite3.connect(args.db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        if args.cmd == "list-corrections":
            payload = list_semantic_review_submissions(
                conn,
                source=str(args.source),
                run_id=str(args.run_id or "") or None,
                limit=max(1, int(args.limit)),
            )
        else:
            record = json.loads(str(args.payload_json))
            payload = submit_semantic_review_submission(
                conn,
                submission_id=str(record["correction_submission_id"]),
                source=str(record["source"]),
                run_id=str(record["run_id"]),
                corpus_label=str(record.get("corpus_label") or record["source"]),
                event_id=str(record["event_id"]),
                relation_id=str(record["relation_id"]) if record.get("relation_id") is not None else None,
                anchor_key=str(record["anchor_key"]) if record.get("anchor_key") is not None else None,
                action_kind=str(record["action_kind"]),
                proposed_payload=record.get("proposed_payload", {}),
                evidence_refs=record.get("evidence_refs", []),
                operator_provenance=record.get("operator_provenance", {}),
                note=str(record.get("note") or ""),
                created_at=str(record["created_at"]),
            )
            conn.commit()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
