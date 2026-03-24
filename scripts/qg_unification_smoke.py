"""Smoke utility for the QG/DA51/SL boundary prototype.

Usage (from repo root):
  PYTHONPATH=. python SensibLaw/scripts/qg_unification_smoke.py
  PYTHONPATH=. python SensibLaw/scripts/qg_unification_smoke.py --json '{"da51":"trace-1","exponents":[1,0,2,0,0,0,0,0,0,0,0,0,0,0,0],"hot":3,"cold":2,"mass":5,"steps":10,"basin":1,"j_fixed":true}'
  PYTHONPATH=. python SensibLaw/scripts/qg_unification_smoke.py --invalid
"""

from __future__ import annotations

import argparse
import json
import sys

# Support running this script from the repo root in a lightweight way.
sys.path.append("SensibLaw")

from src.qg_unification import as_trace_vector, build_dependency_span_payload


def _default_payload() -> dict:
    return {
        "da51": "trace-demo-001",
        "exponents": [1, 0, -1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "hot": 3,
        "cold": 7,
        "mass": 8,
        "steps": 42,
        "basin": 1,
        "j_fixed": False,
    }


def _invalid_payload() -> dict:
    return {
        "da51": "trace-invalid-001",
        "exponents": [1, 0, -1, 2, 0],
        "hot": 1,
        "cold": 2,
        "mass": 3,
        "steps": 4,
        "basin": 0,
        "j_fixed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit DA51Trace -> TraceVector -> envelope")
    parser.add_argument(
        "--json",
        default=None,
        help="JSON object representing DA51Trace payload",
    )
    parser.add_argument(
        "--invalid",
        action="store_true",
        help="Run built-in invalid-payload path to validate error handling.",
    )
    args = parser.parse_args()

    payload = _default_payload()
    if args.json:
        payload = json.loads(args.json)
    if args.invalid:
        payload = _invalid_payload()

    try:
        trace_vector = as_trace_vector(payload)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "invalid_payload": payload,
                    "kind": "validation_failed",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    envelope = build_dependency_span_payload(trace_vector)

    output = {
        "trace_vector": {
            "id": trace_vector.id,
            "exponents": trace_vector.exponents,
            "normalized": trace_vector.normalized,
            "mass": trace_vector.mass,
            "sparsity": trace_vector.sparsity,
            "hot": trace_vector.hot,
            "cold": trace_vector.cold,
            "steps": trace_vector.steps,
            "basin": trace_vector.basin,
            "j_fixed": trace_vector.j_fixed,
            "mdls": trace_vector.mdls,
            "admissible": trace_vector.admissible,
        },
        "envelope": envelope,
    }

    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
