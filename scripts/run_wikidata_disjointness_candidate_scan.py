#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


SCAN_SCHEMA_VERSION = "wikidata_disjointness_scan_candidates/v1"
WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
REQUEST_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "SensibLaw-Wikidata-DisjointnessScan/0.1",
}

SUBCLASS_QUERY = """
SELECT ?holder ?holderLabel ?left ?leftLabel ?right ?rightLabel ?violator ?violatorLabel WHERE {
  ?holder p:P2738 ?stmt .
  ?stmt pq:P11260 ?left, ?right .
  FILTER(?left != ?right)
  FILTER(STR(?left) < STR(?right))
  FILTER NOT EXISTS { ?stmt wikibase:rank wikibase:DeprecatedRank }
  ?violator wdt:P279* ?left, ?right .
  FILTER(?violator != ?left && ?violator != ?right)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT {limit}
""".strip()

INSTANCE_QUERY = """
SELECT ?holder ?holderLabel ?left ?leftLabel ?right ?rightLabel ?violator ?violatorLabel WHERE {
  ?holder p:P2738 ?stmt .
  ?stmt pq:P11260 ?left, ?right .
  FILTER(?left != ?right)
  FILTER(STR(?left) < STR(?right))
  FILTER NOT EXISTS { ?stmt wikibase:rank wikibase:DeprecatedRank }
  ?violator wdt:P31 ?left, ?right .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT {limit}
""".strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan live Wikidata for P2738/P11260 disjointness contradiction candidates."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum rows to request per query kind.",
    )
    parser.add_argument(
        "--query-kind",
        choices=("subclass", "instance", "both"),
        default="both",
        help="Which contradiction query family to run.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def _extract_qid(uri: str) -> str:
    path = urlparse(uri).path.rstrip("/")
    return path.rsplit("/", 1)[-1]


def _binding_text(binding: dict[str, Any], key: str) -> str | None:
    value = binding.get(key)
    if not isinstance(value, dict):
        return None
    raw = value.get("value")
    if not isinstance(raw, str) or not raw:
        return None
    if value.get("type") == "uri":
        return _extract_qid(raw)
    return raw


def _normalize_binding(binding: dict[str, Any], *, violation_kind: str) -> dict[str, Any]:
    row = {
        "holder_qid": _binding_text(binding, "holder"),
        "holder_label": _binding_text(binding, "holderLabel"),
        "left_qid": _binding_text(binding, "left"),
        "left_label": _binding_text(binding, "leftLabel"),
        "right_qid": _binding_text(binding, "right"),
        "right_label": _binding_text(binding, "rightLabel"),
        "violator_qid": _binding_text(binding, "violator"),
        "violator_label": _binding_text(binding, "violatorLabel"),
        "violation_kind": violation_kind,
    }
    missing = [key for key, value in row.items() if key.endswith(("_qid", "_label")) and not value]
    row["rank_score"] = _rank_row(row)
    row["selection_reason"] = (
        "fully labeled direct contradiction candidate"
        if not missing
        else f"candidate with missing fields: {', '.join(sorted(missing))}"
    )
    return row


def _rank_row(row: dict[str, Any]) -> int:
    score = 0
    for key in ("holder_label", "left_label", "right_label", "violator_label"):
        if row.get(key):
            score += 10
    if row.get("violation_kind") == "subclass":
        score += 5
    qids = {row.get("holder_qid"), row.get("left_qid"), row.get("right_qid"), row.get("violator_qid")}
    if None not in qids and len(qids) == 4:
        score += 5
    return score


def _run_query(query: str, *, timeout: int) -> list[dict[str, Any]]:
    response = requests.get(
        WDQS_ENDPOINT,
        params={"query": query},
        headers=REQUEST_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", {}).get("bindings", [])
    if not isinstance(results, list):
        raise ValueError("WDQS response missing results.bindings[]")
    return [item for item in results if isinstance(item, dict)]


def scan_candidates(*, limit: int, query_kind: str, timeout: int) -> dict[str, Any]:
    selected_kinds = ("subclass", "instance") if query_kind == "both" else (query_kind,)
    candidates: list[dict[str, Any]] = []
    for kind in selected_kinds:
        query = SUBCLASS_QUERY if kind == "subclass" else INSTANCE_QUERY
        rendered_query = query.replace("{limit}", str(limit))
        for binding in _run_query(rendered_query, timeout=timeout):
            candidates.append(_normalize_binding(binding, violation_kind=kind))
    candidates.sort(
        key=lambda row: (
            -int(row["rank_score"]),
            str(row["holder_qid"] or ""),
            str(row["left_qid"] or ""),
            str(row["right_qid"] or ""),
            str(row["violator_qid"] or ""),
            str(row["violation_kind"] or ""),
        )
    )
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query_kind": query_kind,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main() -> None:
    args = _parse_args()
    try:
        payload = scan_candidates(limit=args.limit, query_kind=args.query_kind, timeout=args.timeout)
    except requests.RequestException as exc:
        raise SystemExit(f"live WDQS disjointness scan failed: {exc}") from exc
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)


if __name__ == "__main__":
    main()
