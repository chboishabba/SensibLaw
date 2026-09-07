#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
from collections.abc import Callable, Mapping
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_batch_acquisition_dispatch import (  # noqa: E402
    dispatch_acquisition_plan,
)


def _load_executor(spec: str) -> Callable[[Mapping[str, Any]], Mapping[str, Any]]:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("executor must use module:function syntax")
    module = importlib.import_module(module_name)
    executor = getattr(module, attribute)
    if not callable(executor):
        raise TypeError(f"executor is not callable: {spec}")
    return executor


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch a bounded Nat acquisition plan through a named selector executor. "
            "This command emits transport receipts only; it never pays source support, "
            "edits Wikidata, or performs semantic promotion."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--executor",
        required=True,
        help="selector executor callable in module:function form",
    )
    parser.add_argument("--max-tasks", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("expected acquisition-plan JSON object")
    executor = _load_executor(args.executor)
    dispatch = dispatch_acquisition_plan(
        plan,
        selector_executor=executor,
        max_tasks=max(1, int(args.max_tasks)),
    )
    rendered = json.dumps(dispatch, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "dispatch_ref": dispatch["dispatch_ref"],
                    "dispatched_task_count": dispatch["dispatched_task_count"],
                    "counts_by_execution_outcome": dispatch[
                        "counts_by_execution_outcome"
                    ],
                    "network_performed": dispatch["network_performed"],
                    "source_support_paid_count": dispatch[
                        "source_support_paid_count"
                    ],
                    "edits_performed": dispatch["edits_performed"],
                    "semantic_promotion_performed": dispatch[
                        "semantic_promotion_performed"
                    ],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
