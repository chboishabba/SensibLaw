#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_adjudication import (  # noqa: E402
    compile_reviewed_source_decisions,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile explicit reviewed Nat source proposition decisions into exact "
            "verification receipts and source-support admissions. This command does "
            "not perform semantic review itself."
        )
    )
    parser.add_argument("--verification-plan", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    verification_plan = json.loads(args.verification_plan.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    if not isinstance(verification_plan, dict) or not isinstance(decisions, dict):
        raise ValueError("expected JSON objects for verification plan and decisions")

    result = compile_reviewed_source_decisions(verification_plan, decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "adjudication_ref": result["adjudication_ref"],
                "verification_demand_count": result["verification_demand_count"],
                "ready_demand_count": result["ready_demand_count"],
                "blocked_demand_count": result["blocked_demand_count"],
                "reviewed_decision_count": result["reviewed_decision_count"],
                "unreviewed_ready_count": result["unreviewed_ready_count"],
                "counts_by_disposition": result["counts_by_disposition"],
                "source_support_paid_count": result["source_support_paid_count"],
                "source_support_rejected_count": result[
                    "source_support_rejected_count"
                ],
                "source_support_open_reviewed_count": result[
                    "source_support_open_reviewed_count"
                ],
                "authority_evaluated": result["authority_evaluated"],
                "semantic_promotion_performed": result[
                    "semantic_promotion_performed"
                ],
                "migration_authority": result["migration_authority"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
