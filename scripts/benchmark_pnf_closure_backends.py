#!/usr/bin/env python3
"""Benchmark representative PNF operator closure through Python and Zelph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pnf.operator_closure_benchmark import (  # noqa: E402
    NORMALIZED_OPERATOR_RULE_SET_REVISION,
    NormalizedOperatorZelphCodec,
    native_operator_proposals,
)
from src.pnf.streaming_fixed_point import (  # noqa: E402
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
)
from src.pnf.zelph_closure_executor import (  # noqa: E402
    ZelphClosureExecutor,
    ZelphExecutionError,
    benchmark_closure_job,
)
from src.policy.carriers.canonical import canonical_sha256  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _sample_payload() -> dict[str, Any]:
    tokens = [
        {
            "index": 0,
            "text": "Driver",
            "lemma": "driver",
            "pos": "NOUN",
            "dep": "nsubj",
            "head_index": 3,
            "start": 0,
            "end": 6,
        },
        {
            "index": 1,
            "text": "must",
            "lemma": "must",
            "pos": "AUX",
            "dep": "aux",
            "head_index": 3,
            "start": 7,
            "end": 11,
        },
        {
            "index": 2,
            "text": "not",
            "lemma": "not",
            "pos": "PART",
            "dep": "neg",
            "head_index": 3,
            "start": 12,
            "end": 15,
        },
        {
            "index": 3,
            "text": "drive",
            "lemma": "drive",
            "pos": "VERB",
            "dep": "ROOT",
            "head_index": 3,
            "start": 16,
            "end": 21,
        },
        {
            "index": 4,
            "text": "unless",
            "lemma": "unless",
            "pos": "SCONJ",
            "dep": "mark",
            "head_index": 5,
            "start": 22,
            "end": 28,
        },
        {
            "index": 5,
            "text": "licensed",
            "lemma": "license",
            "pos": "VERB",
            "dep": "advcl",
            "head_index": 3,
            "start": 29,
            "end": 37,
        },
    ]
    observations = [
        {
            "observation_ref": "observation:"
            + canonical_sha256({"token": row}),
            "observation_type": "parser.token",
            "token": row,
        }
        for row in tokens
    ]
    return {
        "document_ref": "document:closure-benchmark",
        "scope_ref": "sentence:0",
        "observations": observations,
    }


def _job(payload: dict[str, Any]) -> SolverJob:
    observations = payload["observations"]
    return SolverJob(
        owner_key=OwnerKey(
            str(payload["document_ref"]),
            str(payload["scope_ref"]),
            "semantic.operator_composition",
        ),
        declaration_ref="declaration:normalized-operator:v0_1",
        input_revision=0,
        input_refs=tuple(
            sorted(str(row["observation_ref"]) for row in observations)
        ),
        input_payload={
            "observation_delta": {
                "observations": observations,
            }
        },
        rule_set_revision=NORMALIZED_OPERATOR_RULE_SET_REVISION,
        coverage_requirements=("sentence",),
    )


def main() -> int:
    args = _args()
    payload = (
        json.loads(args.input.read_text(encoding="utf-8"))
        if args.input
        else _sample_payload()
    )
    job = _job(payload)
    python = PythonClosureExecutor(
        {
            "declaration:normalized-operator:v0_1": (
                native_operator_proposals
            )
        }
    )
    zelph = ZelphClosureExecutor(NormalizedOperatorZelphCodec())
    try:
        result = benchmark_closure_job(
            job=job,
            python_executor=python,
            zelph_executor=zelph,
        ).to_dict()
        result["status"] = (
            "parity"
            if result["proposal_digest_equal"]
            and result["reduction_digest_equal"]
            else "mismatch"
        )
    except ZelphExecutionError as error:
        result = {
            "schema_version": "sl.pnf.closure_backend_parity.v0_1",
            "status": "engine_unavailable_or_failed",
            "error": str(error),
            "python_backend_ref": python.backend_ref,
            "zelph_backend_ref": zelph.backend_ref,
            "adopt_backend": False,
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
    result["adopt_backend"] = result.get("status") == "parity"
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result.get("status") in {"parity", "engine_unavailable_or_failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
