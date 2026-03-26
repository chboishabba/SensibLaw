#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from itertools import islice
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
PROFILE_SCHEMA_VERSION = "wikidata_disjointness_local_profile/v1"
PAIR_SEED_SCHEMA_VERSION = "wikidata_disjointness_pair_seed/v1"
WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
REQUEST_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "SensibLaw-Wikidata-DisjointnessScan/0.2",
}
ZELPH_INSTANCE_CANDIDATE_PREDICATE = "sl/disjoint-instance-candidate"
WIKIDATA_INSTANCE_RELATION = "wikidata P31"
QID_RE = re.compile(r"\bQ\d+\b")
PROFILE_DUAL_INSTANCE_PREDICATE = "sl/profile-dual-instance"
PROFILE_DUAL_SUBCLASS_PREDICATE = "sl/profile-dual-subclass"
PROFILE_MIXED_INSTANCE_PREDICATE = "sl/profile-mixed-instance"
PROFILE_MIXED_SUBCLASS_PREDICATE = "sl/profile-mixed-subclass"
PROFILE_CYCLE_PREDICATE = "sl/profile-cycle-peer"
PROFILE_WIDE_SCHEMA_VERSION = "wikidata_disjointness_local_profile_wide/v1"
PROFILE_BOUNDED_SCHEMA_VERSION = "wikidata_disjointness_local_profile_bounded/v1"
PROFILE_EXACT_SCHEMA_VERSION = "wikidata_disjointness_local_profile_exact_qids/v1"
WIDE_PROFILE_PROPERTIES = (
    "P31",
    "P279",
    "P361",
    "P527",
    "P1552",
    "P461",
    "P1696",
    "P2738",
)
BOUNDED_PROFILE_PROBES: dict[str, list[dict[str, str]]] = {
    "P31": [
        {"object_qid": "Q11432", "label": "gas"},
        {"object_qid": "Q11435", "label": "liquid"},
        {"object_qid": "Q2294", "label": "proton"},
        {"object_qid": "Q2348", "label": "neutron"},
    ],
    "P279": [
        {"object_qid": "Q102165", "label": "nucleon"},
        {"object_qid": "Q53617407", "label": "material entity"},
        {"object_qid": "Q124711467", "label": "immaterial entity"},
    ],
    "P361": [
        {"object_qid": "Q102165", "label": "nucleon"},
        {"object_qid": "Q217236", "label": "working fluid"},
    ],
    "P527": [
        {"object_qid": "Q2294", "label": "proton"},
        {"object_qid": "Q2348", "label": "neutron"},
    ],
    "P1552": [
        {"object_qid": "Q11432", "label": "gas"},
    ],
    "P461": [
        {"object_qid": "Q11432", "label": "gas"},
    ],
    "P1696": [
        {"object_qid": "Q11435", "label": "liquid"},
    ],
    "P2738": [
        {"object_qid": "Q102165", "label": "nucleon"},
        {"object_qid": "Q53617489", "label": "independent continuant"},
    ],
}
EXACT_QID_FAMILIES: dict[str, dict[str, Any]] = {
    "working_fluid": {
        "focus_qids": ["Q102205", "Q11432", "Q11435", "Q217236"],
        "probes": [
            {"subject_qid": "Q217236", "pid": "P31", "object_qid": "Q11432", "label": "working fluid instance of gas"},
            {"subject_qid": "Q217236", "pid": "P31", "object_qid": "Q11435", "label": "working fluid instance of liquid"},
            {"subject_qid": "Q102205", "pid": "P2738", "object_qid": None, "label": "fluid disjoint-union statement presence"},
        ],
    },
    "nucleon": {
        "focus_qids": ["Q102165", "Q2294", "Q2348"],
        "probes": [
            {"subject_qid": "Q2294", "pid": "P279", "object_qid": "Q102165", "label": "proton subclass of nucleon"},
            {"subject_qid": "Q2348", "pid": "P279", "object_qid": "Q102165", "label": "neutron subclass of nucleon"},
            {"subject_qid": "Q102165", "pid": "P2738", "object_qid": None, "label": "nucleon disjoint-union statement presence"},
        ],
    },
    "independent_continuant": {
        "focus_qids": ["Q53617489", "Q53617407", "Q124711467", "Q27096213"],
        "probes": [
            {"subject_qid": "Q27096213", "pid": "P279", "object_qid": "Q53617407", "label": "geographic entity subclass of material entity"},
            {"subject_qid": "Q27096213", "pid": "P279", "object_qid": "Q124711467", "label": "geographic entity subclass of immaterial entity"},
            {"subject_qid": "Q53617489", "pid": "P2738", "object_qid": None, "label": "independent continuant disjoint-union statement presence"},
        ],
    },
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
        description="Scan Wikidata for P2738/P11260 disjointness contradiction candidates."
    )
    parser.add_argument(
        "--backend",
        choices=("wdqs", "zelph", "zelph-seedless", "zelph-profile", "zelph-profile-wide", "zelph-profile-bounded", "zelph-profile-exact"),
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
    parser.add_argument(
        "--wide-count-cap",
        type=int,
        default=500,
        help="For --backend zelph-profile-wide: maximum rows counted per property before truncating.",
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


def _run_zelph_query_sample(
    *,
    zelph_command: str,
    zelph_load_path: Path,
    query_line: str,
    example_limit: int,
    count_cap: int,
) -> dict[str, Any]:
    bundle_path = Path("/tmp/wikidata_disjointness_zelph_query.zlp")
    bundle_path.write_text(
        ".lang zelph\n" f".load {zelph_load_path}\n" f"{query_line}\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.Popen(
            [zelph_command, str(bundle_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"zelph backend unavailable: command not found: {zelph_command}") from exc

    observed_count = 0
    truncated = False
    examples: list[dict[str, str]] = []
    assert proc.stdout is not None
    try:
        for raw_line in proc.stdout:
            triples = parse_zelph_inference(raw_line)
            if not triples:
                continue
            for triple in triples:
                subject_qid = _qid_from_zelph_node(triple.get("subject"))
                object_qid = _qid_from_zelph_node(triple.get("object"))
                if not subject_qid or not object_qid:
                    continue
                observed_count += 1
                if len(examples) < example_limit:
                    examples.append({"subject_qid": subject_qid, "object_qid": object_qid})
                if observed_count >= count_cap:
                    truncated = True
                    proc.kill()
                    break
            if truncated:
                break
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    return {
        "observed_count": observed_count,
        "count_exact": not truncated,
        "examples": examples,
    }


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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Build a tiny Zelph script that finds items/classes with two distinct P31 or P279 values.
    # We do not import wikidata.zph to keep startup fast.
    bundle_lines = [".lang zelph", f".load {zelph_load_path}"]
    if seedless_mode in ("p31", "both"):
        bundle_lines.append(
            f'(X "wikidata P31" A, X "wikidata P31" B) => (X "{PROFILE_DUAL_INSTANCE_PREDICATE}" A)'
        )
    if seedless_mode in ("p279", "both"):
        bundle_lines.append(
            f'(X "wikidata P279" A, X "wikidata P279" B) => (X "{PROFILE_DUAL_SUBCLASS_PREDICATE}" A)'
        )
    bundle_lines.extend(
        [
            ".run",
            f'X "{PROFILE_DUAL_INSTANCE_PREDICATE}" META',
            f'X "{PROFILE_DUAL_SUBCLASS_PREDICATE}" META',
        ]
    )
    bundle_text = "\n".join(bundle_lines) + "\n"
    stdout = _run_zelph_bundle(bundle_text, zelph_command=zelph_command)
    subject_buckets: dict[tuple[str, str], set[str]] = {}
    for triple in parse_zelph_inference(stdout):
        predicate = triple.get("predicate")
        if predicate not in {PROFILE_DUAL_INSTANCE_PREDICATE, PROFILE_DUAL_SUBCLASS_PREDICATE}:
            continue
        subject_qid = _qid_from_zelph_node(triple.get("subject"))
        object_qid = _qid_from_zelph_node(triple.get("object"))
        if subject_qid and object_qid:
            subject_buckets.setdefault((predicate, subject_qid), set()).add(object_qid)
    rows: list[dict[str, Any]] = []
    pair_counts: dict[str, int] = {}
    for (predicate, subject_qid), object_qids in subject_buckets.items():
        sorted_qids = sorted(object_qids)
        for idx, left_qid in enumerate(sorted_qids):
            for right_qid in sorted_qids[idx + 1 :]:
                pair_key = "|".join((left_qid, right_qid))
                pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
                if left_qid == right_qid:
                    continue
                if predicate == PROFILE_DUAL_INSTANCE_PREDICATE:
                    violation_kind = "instance"
                    rank_score = 30
                    reason = "seedless local dual-P31 candidate"
                else:
                    violation_kind = "subclass"
                    rank_score = 25
                    reason = "seedless local dual-P279 candidate"
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
                        "violation_kind": violation_kind,
                        "rank_score": rank_score,
                        "selection_reason": reason,
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


def _build_profile_rows(
    *,
    triple_rows: list[dict[str, str]],
    predicate: str,
) -> dict[str, set[str]]:
    buckets: dict[str, set[str]] = {}
    for triple in triple_rows:
        if triple.get("predicate") != predicate:
            continue
        subject_qid = _qid_from_zelph_node(triple.get("subject"))
        object_qid = _qid_from_zelph_node(triple.get("object"))
        if subject_qid and object_qid:
            buckets.setdefault(subject_qid, set()).add(object_qid)
    return buckets


def _scan_profile_zelph(
    *,
    zelph_command: str,
    zelph_load_path: Path,
    limit: int,
) -> dict[str, Any]:
    bundle_lines = [
        ".lang zelph",
        f".load {zelph_load_path}",
        f'(X "wikidata P31" A, X "wikidata P31" B) => (X "{PROFILE_DUAL_INSTANCE_PREDICATE}" A)',
        f'(X "wikidata P279" A, X "wikidata P279" B) => (X "{PROFILE_DUAL_SUBCLASS_PREDICATE}" A)',
        f'(X "wikidata P31" A, X "wikidata P279" B) => (X "{PROFILE_MIXED_INSTANCE_PREDICATE}" A)',
        f'(X "wikidata P31" A, X "wikidata P279" B) => (X "{PROFILE_MIXED_SUBCLASS_PREDICATE}" B)',
        f'(A "wikidata P279" B, B "wikidata P279" A) => (A "{PROFILE_CYCLE_PREDICATE}" B)',
        ".run",
        f'X "{PROFILE_DUAL_INSTANCE_PREDICATE}" META',
        f'X "{PROFILE_DUAL_SUBCLASS_PREDICATE}" META',
        f'X "{PROFILE_MIXED_INSTANCE_PREDICATE}" META',
        f'X "{PROFILE_MIXED_SUBCLASS_PREDICATE}" META',
        f'X "{PROFILE_CYCLE_PREDICATE}" META',
    ]
    stdout = _run_zelph_bundle("\n".join(bundle_lines) + "\n", zelph_command=zelph_command)
    triples = parse_zelph_inference(stdout)

    dual_instance = _build_profile_rows(triple_rows=triples, predicate=PROFILE_DUAL_INSTANCE_PREDICATE)
    dual_subclass = _build_profile_rows(triple_rows=triples, predicate=PROFILE_DUAL_SUBCLASS_PREDICATE)
    mixed_instance = _build_profile_rows(triple_rows=triples, predicate=PROFILE_MIXED_INSTANCE_PREDICATE)
    mixed_subclass = _build_profile_rows(triple_rows=triples, predicate=PROFILE_MIXED_SUBCLASS_PREDICATE)
    cycle_peers = _build_profile_rows(triple_rows=triples, predicate=PROFILE_CYCLE_PREDICATE)

    def _top_examples(buckets: dict[str, set[str]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for subject_qid, object_qids in buckets.items():
            rows.append({"subject_qid": subject_qid, "related_qids": sorted(object_qids)})
        rows.sort(key=lambda row: (-len(row["related_qids"]), row["subject_qid"]))
        return rows[:limit]

    cycle_pairs = set()
    for subject_qid, peers in cycle_peers.items():
        for peer_qid in peers:
            if subject_qid != peer_qid:
                cycle_pairs.add(tuple(sorted((subject_qid, peer_qid))))

    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_limit": limit,
        "source": {"backend": "zelph-profile", "load_path": str(zelph_load_path)},
        "counts": {
            "dual_p31_subject_count": sum(1 for qids in dual_instance.values() if len(qids) >= 2),
            "dual_p279_subject_count": sum(1 for qids in dual_subclass.values() if len(qids) >= 2),
            "mixed_order_subject_count": len(set(mixed_instance) | set(mixed_subclass)),
            "two_cycle_subject_count": len(cycle_peers),
            "two_cycle_pair_count": len(cycle_pairs),
        },
        "examples": {
            "dual_p31": _top_examples({k: v for k, v in dual_instance.items() if len(v) >= 2}),
            "dual_p279": _top_examples({k: v for k, v in dual_subclass.items() if len(v) >= 2}),
            "mixed_order": [
                {
                    "subject_qid": subject_qid,
                    "p31_qids": sorted(mixed_instance.get(subject_qid, set())),
                    "p279_qids": sorted(mixed_subclass.get(subject_qid, set())),
                }
                for subject_qid in sorted(set(mixed_instance) | set(mixed_subclass))
            ][:limit],
            "two_cycle_pairs": [
                {"left_qid": left_qid, "right_qid": right_qid} for left_qid, right_qid in sorted(cycle_pairs)[:limit]
            ],
        },
    }


def _scan_profile_wide_zelph(
    *,
    zelph_command: str,
    zelph_load_path: Path,
    limit: int,
    count_cap: int,
) -> dict[str, Any]:
    bundle_lines = [".lang zelph", f".load {zelph_load_path}"]
    for pid in WIDE_PROFILE_PROPERTIES:
        bundle_lines.append(f'X "wikidata {pid}" Y')
    stdout = _run_zelph_bundle("\n".join(bundle_lines) + "\n", zelph_command=zelph_command)
    property_state: dict[str, dict[str, Any]] = {
        pid: {"observed_count": 0, "count_exact": True, "examples": []} for pid in WIDE_PROFILE_PROPERTIES
    }
    for triple in parse_zelph_inference(stdout):
        predicate = str(triple.get("predicate") or "")
        if not predicate.startswith("wikidata P"):
            continue
        pid = predicate.removeprefix("wikidata ").strip()
        state = property_state.get(pid)
        if state is None:
            continue
        subject_qid = _qid_from_zelph_node(triple.get("subject"))
        object_qid = _qid_from_zelph_node(triple.get("object"))
        if not subject_qid or not object_qid:
            continue
        if state["observed_count"] < count_cap:
            state["observed_count"] += 1
            if len(state["examples"]) < limit:
                state["examples"].append({"subject_qid": subject_qid, "object_qid": object_qid})
        else:
            state["count_exact"] = False
    property_rows = [
        {
            "pid": pid,
            "observed_count": state["observed_count"],
            "count_exact": state["count_exact"],
            "examples": state["examples"],
        }
        for pid, state in property_state.items()
    ]
    nonzero_rows = [row for row in property_rows if int(row["observed_count"]) > 0]
    return {
        "schema_version": PROFILE_WIDE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_limit": limit,
        "count_cap": count_cap,
        "source": {"backend": "zelph-profile-wide", "load_path": str(zelph_load_path)},
        "property_rows": property_rows,
        "summary": {
            "nonzero_property_count": len(nonzero_rows),
            "zero_property_count": len(property_rows) - len(nonzero_rows),
            "nonzero_pids": [row["pid"] for row in nonzero_rows],
        },
    }


def _scan_profile_bounded_zelph(
    *,
    zelph_command: str,
    zelph_load_path: Path,
    limit: int,
    count_cap: int,
) -> dict[str, Any]:
    bundle_lines = [".lang zelph", f".load {zelph_load_path}"]
    for pid, probes in BOUNDED_PROFILE_PROBES.items():
        for probe in probes:
            bundle_lines.append(f'X "wikidata {pid}" "wikidata {probe["object_qid"]}"')
    stdout = _run_zelph_bundle("\n".join(bundle_lines) + "\n", zelph_command=zelph_command)
    probe_state: dict[tuple[str, str], dict[str, Any]] = {}
    for pid, probes in BOUNDED_PROFILE_PROBES.items():
        for probe in probes:
            probe_state[(pid, probe["object_qid"])] = {
                "pid": pid,
                "object_qid": probe["object_qid"],
                "object_label": probe["label"],
                "observed_count": 0,
                "count_exact": True,
                "examples": [],
            }
    for triple in parse_zelph_inference(stdout):
        predicate = str(triple.get("predicate") or "")
        if not predicate.startswith("wikidata P"):
            continue
        pid = predicate.removeprefix("wikidata ").strip()
        object_qid = _qid_from_zelph_node(triple.get("object"))
        subject_qid = _qid_from_zelph_node(triple.get("subject"))
        if not pid or not object_qid or not subject_qid:
            continue
        state = probe_state.get((pid, object_qid))
        if state is None:
            continue
        if state["observed_count"] < count_cap:
            state["observed_count"] += 1
            if len(state["examples"]) < limit:
                state["examples"].append({"subject_qid": subject_qid})
        else:
            state["count_exact"] = False
    probe_rows = list(probe_state.values())
    nonzero_rows = [row for row in probe_rows if int(row["observed_count"]) > 0]
    return {
        "schema_version": PROFILE_BOUNDED_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_limit": limit,
        "count_cap": count_cap,
        "source": {"backend": "zelph-profile-bounded", "load_path": str(zelph_load_path)},
        "probe_rows": probe_rows,
        "summary": {
            "nonzero_probe_count": len(nonzero_rows),
            "zero_probe_count": len(probe_rows) - len(nonzero_rows),
            "nonzero_probes": [
                {"pid": row["pid"], "object_qid": row["object_qid"]} for row in nonzero_rows
            ],
        },
    }


def _scan_profile_exact_zelph(
    *,
    zelph_command: str,
    zelph_load_path: Path,
) -> dict[str, Any]:
    bundle_lines = [".lang zelph", f".load {zelph_load_path}"]
    for family in EXACT_QID_FAMILIES.values():
        for qid in family["focus_qids"]:
            bundle_lines.append(f'"wikidata {qid}" P')
        for probe in family["probes"]:
            subject = probe["subject_qid"]
            pid = probe["pid"]
            object_qid = probe["object_qid"]
            if object_qid:
                bundle_lines.append(f'"wikidata {subject}" "wikidata {pid}" "wikidata {object_qid}"')
            else:
                bundle_lines.append(f'"wikidata {subject}" "wikidata {pid}" O')
    stdout = _run_zelph_bundle("\n".join(bundle_lines) + "\n", zelph_command=zelph_command)
    triples = parse_zelph_inference(stdout)
    subject_presence: dict[str, bool] = {}
    direct_edges: set[tuple[str, str, str]] = set()
    property_presence: set[tuple[str, str]] = set()
    for triple in triples:
        subject_qid = _qid_from_zelph_node(triple.get("subject"))
        predicate = str(triple.get("predicate") or "")
        object_qid = _qid_from_zelph_node(triple.get("object"))
        if subject_qid:
            subject_presence[subject_qid] = True
        if predicate.startswith("wikidata P"):
            pid = predicate.removeprefix("wikidata ").strip()
            if subject_qid and object_qid:
                direct_edges.add((subject_qid, pid, object_qid))
                property_presence.add((subject_qid, pid))
    family_rows: list[dict[str, Any]] = []
    for family_id, family in EXACT_QID_FAMILIES.items():
        qid_rows = [{"qid": qid, "present": bool(subject_presence.get(qid))} for qid in family["focus_qids"]]
        probe_rows = []
        for probe in family["probes"]:
            subject_qid = probe["subject_qid"]
            pid = probe["pid"]
            object_qid = probe["object_qid"]
            if object_qid is None:
                present = (subject_qid, pid) in property_presence
            else:
                present = (subject_qid, pid, object_qid) in direct_edges
            probe_rows.append(
                {
                    "label": probe["label"],
                    "subject_qid": subject_qid,
                    "pid": pid,
                    "object_qid": object_qid,
                    "present": present,
                }
            )
        family_rows.append(
            {
                "family_id": family_id,
                "qid_rows": qid_rows,
                "probe_rows": probe_rows,
            }
        )
    return {
        "schema_version": PROFILE_EXACT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"backend": "zelph-profile-exact", "load_path": str(zelph_load_path)},
        "families": family_rows,
    }


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
    wide_count_cap: int = 500,
) -> dict[str, Any]:
    pair_suggestions: list[dict[str, Any]] = []
    if backend == "zelph-profile":
        if not zelph_load_path:
            raise ValueError("zelph-profile backend requires --zelph-load-path")
        return _scan_profile_zelph(
            zelph_command=zelph_command,
            zelph_load_path=zelph_load_path,
            limit=limit,
        )
    if backend == "zelph-profile-wide":
        if not zelph_load_path:
            raise ValueError("zelph-profile-wide backend requires --zelph-load-path")
        return _scan_profile_wide_zelph(
            zelph_command=zelph_command,
            zelph_load_path=zelph_load_path,
            limit=limit,
            count_cap=wide_count_cap,
        )
    if backend == "zelph-profile-bounded":
        if not zelph_load_path:
            raise ValueError("zelph-profile-bounded backend requires --zelph-load-path")
        return _scan_profile_bounded_zelph(
            zelph_command=zelph_command,
            zelph_load_path=zelph_load_path,
            limit=limit,
            count_cap=wide_count_cap,
        )
    if backend == "zelph-profile-exact":
        if not zelph_load_path:
            raise ValueError("zelph-profile-exact backend requires --zelph-load-path")
        return _scan_profile_exact_zelph(
            zelph_command=zelph_command,
            zelph_load_path=zelph_load_path,
        )
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
            wide_count_cap=args.wide_count_cap,
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
