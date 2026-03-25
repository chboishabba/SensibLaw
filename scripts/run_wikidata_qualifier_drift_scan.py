#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from cli_runtime import build_progress_callback, configure_cli_logging


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata import (  # noqa: E402
    DEFAULT_FIND_QUALIFIER_PROPERTIES,
    REQUEST_HEADERS,
    build_slice_from_entity_exports,
    find_qualifier_drift_candidates,
    project_wikidata_payload,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Wikidata qualifier-drift finder and materialize the first confirmed case."
    )
    parser.add_argument(
        "--property",
        action="append",
        help="Repeatable property filter. Defaults to P166, P39, P54, and P6.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=10,
        help="Maximum number of ranked candidates to scan.",
    )
    parser.add_argument(
        "--revision-limit",
        type=int,
        default=4,
        help="Maximum number of recent revisions to inspect per candidate.",
    )
    parser.add_argument(
        "--query-timeout",
        type=int,
        default=90,
        help="Per-request timeout in seconds for SPARQL/API/entity-export fetches.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/tmp/wikidata_qualifier_scan"),
        help="Directory for the scan report and any materialized case files.",
    )
    parser.add_argument(
        "--no-materialize",
        action="store_true",
        help="Do not download entity exports or build/project a confirmed case.",
    )
    parser.add_argument("--progress", action="store_true", help="Emit progress to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json", "bar"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _download_json(url: str, out_path: Path) -> dict:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    payload = response.json()
    _write_json(out_path, payload)
    return payload


def _materialize_first_case(report: dict, out_dir: Path, *, progress_callback=None) -> dict | None:
    confirmed = report.get("confirmed_drift_cases", [])
    if not confirmed:
        return None
    case = confirmed[0]
    stem = case["suggested_fixture_stem"]
    case_dir = out_dir / stem
    case_dir.mkdir(parents=True, exist_ok=True)

    if callable(progress_callback):
        progress_callback("materialize_download_started", {"section": "wikidata_materialize", "completed": 0, "total": 4, "message": "Downloading first entity export."})
    from_payload = _download_json(case["entity_export_urls"]["from"], case_dir / "from_entity.json")
    if callable(progress_callback):
        progress_callback("materialize_download_progress", {"section": "wikidata_materialize", "completed": 1, "total": 4, "message": "Downloaded from_entity export."})
    to_payload = _download_json(case["entity_export_urls"]["to"], case_dir / "to_entity.json")
    if callable(progress_callback):
        progress_callback("materialize_download_progress", {"section": "wikidata_materialize", "completed": 2, "total": 4, "message": "Downloaded to_entity export."})

    from_payload["_source_path"] = str(case_dir / "from_entity.json")
    to_payload["_source_path"] = str(case_dir / "to_entity.json")
    slice_payload = build_slice_from_entity_exports(
        {"t1": [from_payload], "t2": [to_payload]},
        property_filter=(case["property_pid"],),
    )
    slice_path = case_dir / "slice.json"
    _write_json(slice_path, slice_payload)

    projection = project_wikidata_payload(
        slice_payload,
        property_filter=(case["property_pid"],),
    )
    projection_path = case_dir / "projection.json"
    _write_json(projection_path, projection)
    if callable(progress_callback):
        progress_callback("materialize_download_finished", {"section": "wikidata_materialize", "completed": 4, "total": 4, "message": "Materialized first confirmed case."})

    return {
        "case_dir": str(case_dir),
        "from_entity": str(case_dir / "from_entity.json"),
        "to_entity": str(case_dir / "to_entity.json"),
        "slice": str(slice_path),
        "projection": str(projection_path),
    }


def main() -> None:
    args = _parse_args()
    configure_cli_logging(args.log_level)
    progress_callback = build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format))
    properties = tuple(sorted(set(args.property or DEFAULT_FIND_QUALIFIER_PROPERTIES)))
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if callable(progress_callback):
        progress_callback("scan_started", {"section": "wikidata_scan", "completed": 0, "total": max(int(args.candidate_limit), 1), "message": "Scanning qualifier drift candidates."})
    report = find_qualifier_drift_candidates(
        property_filter=properties,
        candidate_limit=args.candidate_limit,
        revision_limit=args.revision_limit,
        timeout_seconds=args.query_timeout,
        progress_callback=progress_callback,
    )
    if callable(progress_callback):
        progress_callback(
            "scan_finished",
            {
                "section": "wikidata_scan",
                "completed": int(report.get("candidate_count") or 0),
                "total": max(int(args.candidate_limit), int(report.get("candidate_count") or 0), 1),
                "message": f"Scan finished with {len(report.get('confirmed_drift_cases', []))} confirmed cases.",
            },
        )
    report_path = out_dir / "scan_report.json"
    _write_json(report_path, report)

    materialized = None
    if not args.no_materialize:
        materialized = _materialize_first_case(report, out_dir, progress_callback=progress_callback)

    summary = {
        "report": str(report_path),
        "properties": list(properties),
        "candidate_count": report["candidate_count"],
        "confirmed_drift_case_count": len(report["confirmed_drift_cases"]),
        "stable_baseline_count": len(report["stable_baselines"]),
        "failure_count": len(report["failures"]),
        "query_timeout": args.query_timeout,
        "first_confirmed_case": None,
        "materialized": materialized,
    }
    if report["confirmed_drift_cases"]:
        case = report["confirmed_drift_cases"][0]
        summary["first_confirmed_case"] = {
            "qid": case["qid"],
            "property_pid": case["property_pid"],
            "from_revision": case["from_revision"]["revid"],
            "to_revision": case["to_revision"]["revid"],
            "severity": case["qualifier_drift"][0]["severity"],
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
