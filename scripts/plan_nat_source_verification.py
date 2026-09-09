#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_support_verification import (  # noqa: E402
    build_source_verification_plan,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind fetched Nat source artifacts to the exact migration-pack propositions. "
            "This emits verification demands only; it performs no semantic verification."
        )
    )
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--source-dispatch", type=Path, required=True)
    parser.add_argument(
        "--migration-pack",
        type=Path,
        action="append",
        required=True,
        help="Repeat for every migration-pack JSON contributing candidates.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = build_source_verification_plan(
        batch=_load(args.batch),
        source_plan=_load(args.source_plan),
        source_dispatch=_load(args.source_dispatch),
        migration_packs=[_load(path) for path in args.migration_pack],
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
                "ready_count": plan["ready_count"],
                "blocked_count": plan["blocked_count"],
                "source_support_paid_count": 0,
                "authority_evaluated": False,
                "semantic_promotion_performed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
