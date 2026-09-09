#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_filtered_route_request import build_filtered_route_request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile a route-blocked Nat dispatch into one bounded filtered route-sidecar request."
    )
    parser.add_argument("--plan", required=True, help="Path to sl.nat_batch_acquisition_plan.v0_1 JSON")
    parser.add_argument("--dispatch", required=True, help="Path to sl.nat_batch_acquisition_dispatch.v0_1 JSON")
    parser.add_argument("--output", required=True, help="Output request JSON path")
    return parser.parse_args()


def load_json(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    args = parse_args()
    request = build_filtered_route_request(load_json(args.plan), load_json(args.dispatch))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"request_ref={request['request_ref']}")
    print(f"qid_count={request['qid_count']}")
    print("qids=" + ",".join(request["qids"]))
    print(f"producer={request['producer']['repository']}@{request['producer']['commit']}")
    print("network_performed=false")
    print("source_support_paid=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
