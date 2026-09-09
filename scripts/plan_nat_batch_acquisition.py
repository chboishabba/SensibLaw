#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_batch_acquisition_plan import build_acquisition_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a dry Nat prerequisite batch into bounded Zelph/HF acquisition "
            "tasks. Performs no network requests, edits, verification, or promotion."
        )
    )
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    if not isinstance(batch, dict):
        raise ValueError("expected batch JSON object")
    plan = build_acquisition_plan(batch)
    rendered = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "plan_ref": plan["plan_ref"],
                    "planned_task_count": plan["planned_task_count"],
                    "planned_member_count": plan["planned_member_count"],
                    "network_performed": plan["network_performed"],
                    "edits_performed": plan["edits_performed"],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
