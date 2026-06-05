#!/usr/bin/env python3
"""Benchmark Conversation VM compile/reduce stages over small fixtures."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sensiblaw.conversation_vm import compile_turn, empty_state, step_state


def _fixture_turns(mode: str) -> list[dict[str, Any]]:
    if mode == "supplied_atoms":
        return [
            {
                "turn_id": "supplied-1",
                "text": "Supplied atom surface.",
                "predicate_atoms": [
                    {"predicate": "claim", "arguments": ["alpha"], "polarity": "positive", "receipt_ids": ["r1"]}
                ],
            }
        ]
    if mode == "shared_projector":
        return [{"turn_id": f"shared-{idx}", "text": "Alpha supports beta."} for idx in range(4)]
    if mode == "repeated_text":
        text = "Alpha supports beta. " * 40
        return [{"turn_id": "repeated-1", "text": text}]
    if mode == "conflict_density":
        return [
            {
                "turn_id": f"conflict-{idx}",
                "text": "fixture",
                "predicate_atoms": [
                    {
                        "predicate": "claim",
                        "arguments": ["alpha"],
                        "polarity": "negative" if idx % 2 else "positive",
                        "receipt_ids": [f"r{idx}"],
                    }
                ],
            }
            for idx in range(8)
        ]
    if mode == "utterance_pnf_conflict":
        return [
            {"turn_id": "utterance-positive", "text": "I walked the dog."},
            {"turn_id": "utterance-negative", "text": "I did not walk the dog."},
        ]
    if mode == "sparse_atoms":
        return [{"turn_id": "sparse-1", "text": ""}, {"turn_id": "sparse-2", "text": "   \n"}]
    raise ValueError(f"unknown fixture mode: {mode}")


def run_benchmark(mode: str, *, iterations: int = 1) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    state = empty_state()
    started = time.perf_counter()
    turns = _fixture_turns(mode)
    for iteration in range(max(1, iterations)):
        for turn in turns:
            delta = compile_turn({**turn, "turn_id": f"{turn['turn_id']}:{iteration}"}, metrics_callback=metrics.append)
            state = step_state(state, delta, metrics_callback=metrics.append)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 6)
    by_stage: dict[str, dict[str, Any]] = {}
    for row in metrics:
        key = f"{row.get('component')}:{row.get('stage')}"
        bucket = by_stage.setdefault(key, {"count": 0, "elapsed_ms": 0.0})
        bucket["count"] += 1
        bucket["elapsed_ms"] = round(float(bucket["elapsed_ms"]) + float(row.get("elapsed_ms") or 0.0), 6)
    return {
        "schema": "sensiblaw.conversation_vm.benchmark.v0_1",
        "fixture_mode": mode,
        "iterations": max(1, iterations),
        "turn_count": len(turns) * max(1, iterations),
        "elapsed_ms": elapsed_ms,
        "stage_metrics": metrics,
        "stage_summary": by_stage,
        "state_metadata": state.get("compact_payload_metadata", {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-mode",
        choices=["supplied_atoms", "shared_projector", "repeated_text", "conflict_density", "utterance_pnf_conflict", "sparse_atoms"],
        default="shared_projector",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--output", "-o", type=Path)
    args = parser.parse_args(argv)
    payload = run_benchmark(args.fixture_mode, iterations=args.iterations)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
