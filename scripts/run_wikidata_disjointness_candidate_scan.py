#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.zelph_bridge import parse_zelph_inference


SCAN_SCHEMA_VERSION = "wikidata_disjointness_scan_candidates/v1"
PAIR_SEED_SCHEMA_VERSION = "wikidata_disjointness_pair_seed/v1"
WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
REQUEST_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "SensibLaw-Wikidata-DisjointnessScan/0.2",
}
ZELPH_INSTANCE_CANDIDATE_PREDICATE = "sl/disjoint-instance-candidate"
WIKIDATA_INSTANCE_RELATION = "wikidata P31"
QID_RE = re.compile(r"\bQ\d+\b")

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
        description="Scan Wikidata for P2738/P11260 disjointness contradiction candidates."
    )
    parser.add_argument(
        "--backend",
        choices=("wdqs", "zelph", "zelph-seedless"),
        default="wdqs",
        help="Candidate discovery backend.",
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
    parser.add_argument(
        "--pair-seed",
        type=Path,
        help="Disjoint-pair seed JSON. Required for the zelph backend.",
    )
    parser.add_argument(
        "--zelph-command",
        default="zelph",
        help="Path to the zelph executable.",
    )
    parser.add_argument(
        "--zelph-load-path",
        type=Path,
        help="Optional local .bin/.json path loaded via '.load' for the zelph backend.",
    )
    parser.add_argument(
        "--zelph-wikidata-script",
        type=Path,
        help="Optional wikidata.zph path imported after '.load' for the zelph backend.",
    )
    parser.add_argument(
        "--zelph-prelude-path",
        type=Path,
        help="Optional raw zelph script prepended before generated rules. Useful for tests and small local networks.",
    )
    parser.add_argument(
        "--seedless-topn",
        type=int,
        default=50,
        help="For --backend zelph-seedless: cap the number of dual-P31 violators returned.",
    )
    parser.add_argument(
        "--seedless-mode",
        choices=("p31", "p279", "both"),
        default="both",
        help="For --backend zelph-seedless: which dual-relations to search.",
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


def _quote_zelph_text(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _qid_from_zelph_node(text: str | None) -> str | None:
    if not text:
        return None
    match = QID_RE.search(text)
    return match.group(0) if match else None


def _load_pair_seed(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PAIR_SEED_SCHEMA_VERSION:
        raise ValueError(
            f"pair seed at {path} must declare schema_version={PAIR_SEED_SCHEMA_VERSION}"
        )
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"pair seed at {path} must contain a non-empty entries[] list")
    normalized: list[dict[str, str]] = []
    required = (
        "holder_qid",
        "holder_label",
        "left_qid",
        "left_label",
        "right_qid",
        "right_label",
    )
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"pair seed entry {idx} must be an object")
        row = {key: str(entry.get(key) or "").strip() for key in required}
        missing = [key for key, value in row.items() if not value]
        if missing:
            raise ValueError(
                f"pair seed entry {idx} missing required fields: {', '.join(sorted(missing))}"
            )
        normalized.append(row)
    return normalized


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


def _scan_candidates_wdqs(*, limit: int, query_kind: str, timeout: int) -> list[dict[str, Any]]:
    selected_kinds = ("subclass", "instance") if query_kind == "both" else (query_kind,)
    candidates: list[dict[str, Any]] = []
    for kind in selected_kinds:
        query = SUBCLASS_QUERY if kind == "subclass" else INSTANCE_QUERY
        rendered_query = query.replace("{limit}", str(limit))
        for binding in _run_query(rendered_query, timeout=timeout):
            candidates.append(_normalize_binding(binding, violation_kind=kind))
    return candidates


def _render_zelph_instance_bundle(
    *,
    pair_seed: list[dict[str, str]],
    zelph_load_path: Path | None,
    zelph_wikidata_script: Path | None,
    zelph_prelude_text: str | None,
) -> str:
    lines: list[str] = [".lang zelph"]
    if zelph_prelude_text and zelph_prelude_text.strip():
        lines.append(zelph_prelude_text.strip())
    if zelph_load_path:
        lines.append(f".load {zelph_load_path}")
    if zelph_wikidata_script:
        lines.append(f".import {zelph_wikidata_script}")
    for entry in pair_seed:
        metadata = "|".join((entry["holder_qid"], entry["left_qid"], entry["right_qid"]))
        lines.append(
            "("
            f'X {_quote_zelph_text(WIKIDATA_INSTANCE_RELATION)} {_quote_zelph_text("wikidata " + entry["left_qid"])}, '
            f'X {_quote_zelph_text(WIKIDATA_INSTANCE_RELATION)} {_quote_zelph_text("wikidata " + entry["right_qid"])}'
            ") => "
            f'(X {_quote_zelph_text(ZELPH_INSTANCE_CANDIDATE_PREDICATE)} {_quote_zelph_text(metadata)})'
        )
    lines.append(".run")
    lines.append(f'X {_quote_zelph_text(ZELPH_INSTANCE_CANDIDATE_PREDICATE)} META')
    return "\n".join(lines) + "\n"


def _run_zelph_bundle(bundle_text: str, *, zelph_command: str) -> str:
    bundle_path = Path("/tmp/wikidata_disjointness_zelph_scan.zlp")
    bundle_path.write_text(bundle_text, encoding="utf-8")
    try:
        result = subprocess.run(
            [zelph_command, str(bundle_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"zelph backend unavailable: command not found: {zelph_command}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("zelph backend timed out") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        details = stderr or stdout or "unknown zelph failure"
        raise RuntimeError(f"zelph backend failed: {details}") from exc
    return result.stdout


def _scan_candidates_zelph(
    *,
    query_kind: str,
    pair_seed_path: Path | None,
    zelph_command: str,
    zelph_load_path: Path | None,
    zelph_wikidata_script: Path | None,
    zelph_prelude_path: Path | None,
) -> list[dict[str, Any]]:
    if query_kind != "instance":
        raise ValueError("zelph backend currently supports only --query-kind instance")
    if not pair_seed_path:
        raise ValueError("zelph backend requires --pair-seed")
    if not zelph_load_path and not zelph_prelude_path:
        raise ValueError("zelph backend requires --zelph-load-path or --zelph-prelude-path")
    pair_seed = _load_pair_seed(pair_seed_path)
    pair_lookup = {
        "|".join((entry["holder_qid"], entry["left_qid"], entry["right_qid"])): entry for entry in pair_seed
    }
    prelude_text = (
        zelph_prelude_path.read_text(encoding="utf-8") if zelph_prelude_path else None
    )
    bundle_text = _render_zelph_instance_bundle(
        pair_seed=pair_seed,
        zelph_load_path=zelph_load_path,
        zelph_wikidata_script=zelph_wikidata_script,
        zelph_prelude_text=prelude_text,
    )
    stdout = _run_zelph_bundle(bundle_text, zelph_command=zelph_command)
    rows: list[dict[str, Any]] = []
    for triple in parse_zelph_inference(stdout):
        if triple.get("predicate") != ZELPH_INSTANCE_CANDIDATE_PREDICATE:
            continue
        metadata = str(triple.get("object") or "").strip()
        seed = pair_lookup.get(metadata)
        if not seed:
            continue
        violator_qid = _qid_from_zelph_node(str(triple.get("subject") or ""))
        row = {
            "holder_qid": seed["holder_qid"],
            "holder_label": seed["holder_label"],
            "left_qid": seed["left_qid"],
            "left_label": seed["left_label"],
            "right_qid": seed["right_qid"],
            "right_label": seed["right_label"],
            "violator_qid": violator_qid,
            "violator_label": violator_qid,
            "violation_kind": "instance",
        }
        row["rank_score"] = _rank_row(row)
        row["selection_reason"] = (
            "local zelph instance contradiction candidate from explicit disjoint-pair seed"
        )
        rows.append(row)
    return rows


def _scan_candidates_zelph_seedless(
    *,
    zelph_command: str,
    zelph_load_path: Path,
    seedless_topn: int,
    seedless_mode: str,
) -> list[dict[str, Any]]:
    # Build a tiny Zelph script that finds items/classes with two distinct P31 or P279 values.
    # We do not import wikidata.zph to keep startup fast.
    bundle_lines = [".lang zelph", f".load {zelph_load_path}"]
    if seedless_mode in ("p31", "both"):
        bundle_lines.append(
            '(X "wikidata P31" A, X "wikidata P31" B, A != B) => (X "sl/dual-instance" (A B))'
        )
    if seedless_mode in ("p279", "both"):
        bundle_lines.append(
            '(X "wikidata P279" A, X "wikidata P279" B, A != B) => (X "sl/dual-subclass" (A B))'
        )
    bundle_lines.extend(
        [
            ".run",
            'X "sl/dual-instance" META',
            'X "sl/dual-subclass" META',
        ]
    )
    bundle_text = "\n".join(bundle_lines) + "\n"
    stdout = _run_zelph_bundle(bundle_text, zelph_command=zelph_command)
    rows: list[dict[str, Any]] = []
    pair_counts: dict[str, int] = {}
    for triple in parse_zelph_inference(stdout):
        predicate = triple.get("predicate")
        if predicate not in {"sl/dual-instance", "sl/dual-subclass"}:
            continue
        subject_qid = _qid_from_zelph_node(triple.get("subject"))
        obj_text = str(triple.get("object") or "")
        # crude parse: expect "(Q1 Q2)" style; fall back to splitting on space
        parts = QID_RE.findall(obj_text)
        if subject_qid and len(parts) >= 2:
            left_qid, right_qid = parts[:2]
            pair_key = "|".join(sorted((left_qid, right_qid)))
            pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
            rows.append(
                {
                    "holder_qid": "seedless",
                    "holder_label": "seedless",
                    "left_qid": left_qid,
                    "left_label": left_qid,
                    "right_qid": right_qid,
                    "right_label": right_qid,
                    "violator_qid": subject_qid,
                    "violator_label": subject_qid,
                    "violation_kind": "instance"
                    if predicate == "sl/dual-instance"
                    else "subclass",
                    "rank_score": 30 if predicate == "sl/dual-instance" else 25,
                    "selection_reason": "seedless local dual-P31 candidate"
                    if predicate == "sl/dual-instance"
                    else "seedless local dual-P279 candidate",
                }
            )
    rows.sort(
        key=lambda row: (
            str(row["left_qid"] or ""),
            str(row["right_qid"] or ""),
            str(row["violator_qid"] or ""),
        )
    )
    pair_suggestions = [
        {"pair_key": key, "count": count} for key, count in sorted(pair_counts.items(), key=lambda kv: -kv[1])
    ][: seedless_topn]
    return rows[:seedless_topn], pair_suggestions


def scan_candidates(
    *,
    backend: str,
    limit: int,
    query_kind: str,
    timeout: int,
    pair_seed_path: Path | None = None,
    zelph_command: str = "zelph",
    zelph_load_path: Path | None = None,
    zelph_wikidata_script: Path | None = None,
    zelph_prelude_path: Path | None = None,
    seedless_topn: int = 50,
    seedless_mode: str = "both",
) -> dict[str, Any]:
    pair_suggestions: list[dict[str, Any]] = []
    if backend == "wdqs":
        candidates = _scan_candidates_wdqs(limit=limit, query_kind=query_kind, timeout=timeout)
    elif backend == "zelph":
        candidates = _scan_candidates_zelph(
            query_kind=query_kind,
            pair_seed_path=pair_seed_path,
            zelph_command=zelph_command,
            zelph_load_path=zelph_load_path,
            zelph_wikidata_script=zelph_wikidata_script,
            zelph_prelude_path=zelph_prelude_path,
        )
    elif backend == "zelph-seedless":
        if not zelph_load_path:
            raise ValueError("zelph-seedless backend requires --zelph-load-path")
        candidates, pair_suggestions = _scan_candidates_zelph_seedless(
            zelph_command=zelph_command,
            zelph_load_path=zelph_load_path,
            seedless_topn=seedless_topn,
            seedless_mode=seedless_mode,
        )
    else:
        raise ValueError(f"unsupported backend: {backend}")
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
        "pair_suggestions": pair_suggestions if backend == "zelph-seedless" else [],
    }


def main() -> None:
    args = _parse_args()
    try:
        payload = scan_candidates(
            backend=args.backend,
            limit=args.limit,
            query_kind=args.query_kind,
            timeout=args.timeout,
            pair_seed_path=args.pair_seed,
            zelph_command=args.zelph_command,
            zelph_load_path=args.zelph_load_path,
            zelph_wikidata_script=args.zelph_wikidata_script,
            zelph_prelude_path=args.zelph_prelude_path,
            seedless_topn=args.seedless_topn,
            seedless_mode=args.seedless_mode,
        )
    except requests.RequestException as exc:
        raise SystemExit(f"live WDQS disjointness scan failed: {exc}") from exc
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)


if __name__ == "__main__":
    main()
