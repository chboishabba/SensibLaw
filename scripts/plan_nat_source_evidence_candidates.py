#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_evidence_candidates import (  # noqa: E402
    build_source_evidence_candidate_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile exact Nat source-verification demands to page/character evidence "
            "candidates over materialized canonical text. Candidate spans do not pay "
            "source support."
        )
    )
    parser.add_argument("--verification-plan", type=Path, required=True)
    parser.add_argument("--media-dispatch", type=Path, required=True)
    parser.add_argument("--materialized-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-candidates-per-demand", type=int, default=8)
    parser.add_argument("--window-chars", type=int, default=500)
    args = parser.parse_args()

    verification_plan = json.loads(args.verification_plan.read_text(encoding="utf-8"))
    media_dispatch = json.loads(args.media_dispatch.read_text(encoding="utf-8"))
    if not isinstance(verification_plan, dict) or not isinstance(media_dispatch, dict):
        raise ValueError("expected JSON objects for verification plan and media dispatch")

    plan = build_source_evidence_candidate_plan(
        verification_plan,
        media_dispatch,
        materialized_store_dir=args.materialized_dir,
        max_candidates_per_demand=max(1, int(args.max_candidates_per_demand)),
        window_chars=max(1, int(args.window_chars)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "plan_ref": plan["plan_ref"],
                "demand_count": plan["demand_count"],
                "candidate_count": plan["candidate_count"],
                "demands_with_candidates_count": plan[
                    "demands_with_candidates_count"
                ],
                "open_no_quantity_anchor_count": plan[
                    "open_no_quantity_anchor_count"
                ],
                "blocked_count": plan["blocked_count"],
                "source_support_paid_count": plan["source_support_paid_count"],
                "authority_evaluated": plan["authority_evaluated"],
                "semantic_promotion_performed": plan[
                    "semantic_promotion_performed"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
