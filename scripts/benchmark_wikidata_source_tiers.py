#!/usr/bin/env python3
"""Benchmark Zelph/HF snapshot-first Wikidata acquisition against live lookup.

The harness intentionally benchmarks acquisition transports, not semantic
correctness.  Feed the same labels and (Q,P) keys to snapshot-only, tiered and
live-only transports and compare:

- wall-clock latency;
- candidate/property coverage;
- acquisition-call count;
- fallback fraction.

Factories are supplied as ``module:callable`` and must return objects satisfying
``WikidataTransport``.  This keeps the benchmark independent of whether the
Zelph backend is an already-loaded local process, an ITIR HF shard connector, or
a later native binding.

Workload JSON shape:

    {
      "labels": ["Springfield", "Ronald Reagan"],
      "properties": [[180672, 17], [9960, 31]]
    }
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Callable, Sequence

from src.policy.wikidata_late_provider import WikidataTransport
from src.policy.wikidata_tiered_transport import TieredWikidataTransport, WikidataTierPolicy


def _factory(spec: str) -> Callable[[], WikidataTransport]:
    module_name, separator, callable_name = spec.partition(":")
    if not separator or not module_name or not callable_name:
        raise ValueError("factory must be module:callable")
    module = importlib.import_module(module_name)
    factory = getattr(module, callable_name)
    if not callable(factory):
        raise TypeError(f"factory is not callable: {spec}")
    return factory


def _workload(path: Path) -> tuple[tuple[str, ...], tuple[tuple[int, int], ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = tuple(dict.fromkeys(str(value) for value in payload.get("labels", []) if str(value)))
    properties = tuple(
        sorted(
            set(
                (int(row[0]), int(row[1]))
                for row in payload.get("properties", [])
                if isinstance(row, list) and len(row) == 2
            )
        )
    )
    return labels, properties


def _one(
    transport: WikidataTransport,
    *,
    labels: Sequence[str],
    properties: Sequence[tuple[int, int]],
    candidate_limit: int,
) -> dict[str, object]:
    started = perf_counter()
    search = transport.search_entities(labels, limit_per_label=candidate_limit)
    property_batch = transport.fetch_properties(properties)
    elapsed = perf_counter() - started
    candidate_hits = sum(bool(search.candidates_by_label.get(label)) for label in labels)
    property_hits = sum(bool(property_batch.facts_by_key.get(key)) for key in properties)
    return {
        "elapsed_seconds": elapsed,
        "candidate_hits": candidate_hits,
        "candidate_total": len(labels),
        "candidate_hit_fraction": (candidate_hits / len(labels) if labels else 1.0),
        "property_hits": property_hits,
        "property_total": len(properties),
        "property_hit_fraction": (property_hits / len(properties) if properties else 1.0),
        "acquisition_call_count": search.provider_call_count + property_batch.provider_call_count,
    }


def _measure(
    factory: Callable[[], WikidataTransport],
    *,
    labels: Sequence[str],
    properties: Sequence[tuple[int, int]],
    candidate_limit: int,
    repeats: int,
    warmups: int,
) -> dict[str, object]:
    transport = factory()
    for _ in range(warmups):
        _one(
            transport,
            labels=labels,
            properties=properties,
            candidate_limit=candidate_limit,
        )
    rows = [
        _one(
            transport,
            labels=labels,
            properties=properties,
            candidate_limit=candidate_limit,
        )
        for _ in range(repeats)
    ]
    times = [float(row["elapsed_seconds"]) for row in rows]
    calls = [int(row["acquisition_call_count"]) for row in rows]
    final = rows[-1]
    return {
        **{key: value for key, value in final.items() if key != "elapsed_seconds"},
        "median_elapsed_seconds": median(times),
        "min_elapsed_seconds": min(times),
        "max_elapsed_seconds": max(times),
        "median_acquisition_call_count": median(calls),
        "repeats": repeats,
        "warmups": warmups,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--snapshot-factory", required=True)
    parser.add_argument("--live-factory")
    parser.add_argument("--candidate-limit", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 0:
        raise ValueError("repeats must be positive and warmups non-negative")

    labels, properties = _workload(args.workload)
    snapshot_factory = _factory(args.snapshot_factory)
    live_factory = _factory(args.live_factory) if args.live_factory else None

    report: dict[str, object] = {
        "workload": {
            "label_count": len(labels),
            "property_key_count": len(properties),
        },
        "snapshot_only": _measure(
            snapshot_factory,
            labels=labels,
            properties=properties,
            candidate_limit=args.candidate_limit,
            repeats=args.repeats,
            warmups=args.warmups,
        ),
    }

    if live_factory is not None:
        report["live_only"] = _measure(
            live_factory,
            labels=labels,
            properties=properties,
            candidate_limit=args.candidate_limit,
            repeats=args.repeats,
            warmups=args.warmups,
        )

        def tiered_factory() -> WikidataTransport:
            return TieredWikidataTransport(
                snapshot_factory(),
                live_factory(),
                policy=WikidataTierPolicy(
                    fallback_on_snapshot_miss=True,
                    require_live_discovery=args.require_live,
                    require_live_properties=args.require_live,
                ),
            )

        report["snapshot_then_live"] = _measure(
            tiered_factory,
            labels=labels,
            properties=properties,
            candidate_limit=args.candidate_limit,
            repeats=args.repeats,
            warmups=args.warmups,
        )
        snapshot = report["snapshot_only"]
        tiered = report["snapshot_then_live"]
        assert isinstance(snapshot, dict) and isinstance(tiered, dict)
        report["derived"] = {
            "snapshot_candidate_coverage": snapshot["candidate_hit_fraction"],
            "snapshot_property_coverage": snapshot["property_hit_fraction"],
            "tiered_extra_calls_over_snapshot": float(tiered["median_acquisition_call_count"])
            - float(snapshot["median_acquisition_call_count"]),
            "freshness_forced": bool(args.require_live),
        }

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
