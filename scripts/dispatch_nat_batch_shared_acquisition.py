#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_batch_shared_acquisition_dispatch import (  # noqa: E402
    dispatch_shared_acquisition_plan,
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
            "Dispatch a bounded Nat acquisition plan as one shared union selector "
            "execution followed by task-local and residual-local projections."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--executor", required=True)
    parser.add_argument("--max-tasks", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("expected acquisition-plan JSON object")
    dispatch = dispatch_shared_acquisition_plan(
        plan,
        selector_executor=_load_executor(args.executor),
        max_tasks=max(1, int(args.max_tasks)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dispatch, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "dispatch_ref": dispatch["dispatch_ref"],
                "executor_call_count": dispatch["executor_call_count"],
                "projection_count": dispatch["projection_count"],
                "shared_union_qids": dispatch["shared_execution"]["selector"]["qids"],
                "counts_by_execution_outcome": dispatch["counts_by_execution_outcome"],
                "planned_live_coverage_residual_count": dispatch.get(
                    "planned_live_coverage_residual_count", 0
                ),
                "residual_recomputation_count": dispatch.get(
                    "residual_recomputation_count", 0
                ),
                "coverage_residual_paid_count": dispatch.get(
                    "coverage_residual_paid_count", 0
                ),
                "coverage_residual_still_open_count": dispatch.get(
                    "coverage_residual_still_open_count", 0
                ),
                "ternary_admissibility_projection_count": dispatch.get(
                    "ternary_admissibility_projection_count", 0
                ),
                "network_performed": dispatch["network_performed"],
                "source_support_paid_count": dispatch["source_support_paid_count"],
                "consumer_verification_performed": dispatch.get(
                    "consumer_verification_performed", False
                ),
                "semantic_promotion_performed": dispatch.get(
                    "semantic_promotion_performed", False
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
