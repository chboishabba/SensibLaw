#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
THIS_DIR = Path(__file__).resolve().parent
ARTIFACT_VERSION = "au_broader_corpus_diagnostics_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from build_au_corpus_scorecard import (  # noqa: E402
    DEFAULT_BUNDLE_PATHS,
    DEFAULT_RAW_SOURCE_ROOT,
    _build_slice,
    _coerce_path,
    _collect_paths,
)


def _workflow_summaries(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in slice_payload["bundle_inventory"]:
        workflow_kind = str(row.get("workflow_kind") or "")
        bucket = grouped.setdefault(
            workflow_kind,
            {
                "workflow_kind": workflow_kind,
                "bundle_count": 0,
                "source_label_count": 0,
                "fact_count_total": 0,
                "observation_count_total": 0,
                "event_count_total": 0,
                "review_queue_count_total": 0,
                "contested_item_count_total": 0,
                "source_labels": set(),
            },
        )
        bucket["bundle_count"] += 1
        bucket["fact_count_total"] += int(row.get("fact_count") or 0)
        bucket["observation_count_total"] += int(row.get("observation_count") or 0)
        bucket["event_count_total"] += int(row.get("event_count") or 0)
        bucket["review_queue_count_total"] += int(row.get("review_queue_count") or 0)
        bucket["contested_item_count_total"] += int(row.get("contested_item_count") or 0)
        source_label = str(row.get("source_label") or "")
        if source_label:
            bucket["source_labels"].add(source_label)
    rows: list[dict[str, Any]] = []
    for bucket in grouped.values():
        labels = sorted(bucket.pop("source_labels"))
        bucket["source_label_count"] = len(labels)
        bucket["source_labels"] = labels
        rows.append(bucket)
    rows.sort(key=lambda row: row["workflow_kind"])
    return rows


def _bundle_pressure_inventory(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in slice_payload["bundle_inventory"]:
        rows.append(
            {
                "bundle_path": row["bundle_path"],
                "workflow_kind": row["workflow_kind"],
                "source_label": row["source_label"],
                "review_queue_count": int(row.get("review_queue_count") or 0),
                "contested_item_count": int(row.get("contested_item_count") or 0),
                "event_count": int(row.get("event_count") or 0),
                "fact_count": int(row.get("fact_count") or 0),
                "pressure_score": int(row.get("review_queue_count") or 0) + int(row.get("contested_item_count") or 0),
            }
        )
    rows.sort(key=lambda row: (-row["pressure_score"], -row["event_count"], row["source_label"]))
    return rows


def _build_summary(slice_payload: dict[str, Any], workflow_summaries: list[dict[str, Any]], pressure_inventory: list[dict[str, Any]]) -> dict[str, Any]:
    summary = slice_payload["summary"]
    return {
        "source_family_count": len(slice_payload["bundle_inventory"]),
        "workflow_kind_count": len(workflow_summaries),
        "transcript_semantic_bundle_count": sum(1 for row in slice_payload["bundle_inventory"] if row["workflow_kind"] == "transcript_semantic"),
        "bundles_with_events_count": sum(1 for row in slice_payload["bundle_inventory"] if int(row.get("event_count") or 0) > 0),
        "bundles_with_contested_items_count": sum(1 for row in slice_payload["bundle_inventory"] if int(row.get("contested_item_count") or 0) > 0),
        "known_raw_transcript_file_count": int(summary["known_raw_transcript_file_count"]),
        "fact_count_total": int(summary["fact_count_total"]),
        "observation_count_total": int(summary["observation_count_total"]),
        "review_queue_count_total": int(summary["review_queue_count_total"]),
        "peak_pressure_bundle": pressure_inventory[0]["source_label"] if pressure_inventory else "",
        "core_reading": "AU broader corpus coverage now spans multiple real workbench bundles and transcript-semantic lanes, but full transcript-derived event coverage still sits in a visible raw-source backlog.",
    }


def _build_summary_text(payload: dict[str, Any]) -> str:
    lines = [
        "# AU Broader Corpus Diagnostics Summary",
        "",
        "This artifact complements the AU handoff and corpus scorecard by",
        "showing where the current broader AU pressure sits across real bundles",
        "and where raw transcript backlog remains visible.",
        "",
        "## Headline",
        "",
        f"- Real bundles inspected: {payload['summary']['source_family_count']}",
        f"- Workflow kinds: {payload['summary']['workflow_kind_count']}",
        f"- Transcript-semantic bundles: {payload['summary']['transcript_semantic_bundle_count']}",
        f"- Bundles with explicit events: {payload['summary']['bundles_with_events_count']}",
        f"- Bundles with contested items: {payload['summary']['bundles_with_contested_items_count']}",
        f"- Known raw transcript files still outside the bundle checkpoint: {payload['summary']['known_raw_transcript_file_count']}",
        "",
        f"- Reading: {payload['summary']['core_reading']}",
        "",
        "## Workflow summaries",
        "",
    ]
    for row in payload["workflow_summaries"]:
        lines.append(
            f"- {row['workflow_kind']}: bundles={row['bundle_count']}, "
            f"facts={row['fact_count_total']}, observations={row['observation_count_total']}, "
            f"events={row['event_count_total']}, review_queue={row['review_queue_count_total']}, "
            f"contested={row['contested_item_count_total']}."
        )
    lines.extend(["", "## Highest review-pressure bundles", ""])
    for row in payload["bundle_pressure_inventory"][:4]:
        lines.append(
            f"- {row['source_label']} ({row['workflow_kind']}): pressure={row['pressure_score']}, "
            f"facts={row['fact_count']}, events={row['event_count']}."
        )
    lines.extend(
        [
            "",
            "## Practical reading",
            "",
            "- AU is no longer just a single 3-fact handoff slice in repo accounting.",
            "- The broader checkpoint already spans multiple real bundles and transcript-semantic review lanes.",
            "- The next AU parity move is to convert more of the visible raw transcript backlog into persisted reviewed bundle coverage rather than only counting the backlog.",
            "",
        ]
    )
    return "\n".join(lines)


def build_diagnostics(
    output_dir: Path,
    *,
    bundle_paths: list[Path] | None = None,
    raw_source_root: Path = DEFAULT_RAW_SOURCE_ROOT,
) -> dict[str, Any]:
    selected_bundle_paths = [path.resolve() for path in (bundle_paths or DEFAULT_BUNDLE_PATHS)]
    slice_payload = _build_slice(selected_bundle_paths, raw_source_root=raw_source_root.resolve())
    workflow_summaries = _workflow_summaries(slice_payload)
    pressure_inventory = _bundle_pressure_inventory(slice_payload)
    payload = {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "au_broader_corpus_diagnostics",
        "summary": _build_summary(slice_payload, workflow_summaries, pressure_inventory),
        "workflow_summaries": workflow_summaries,
        "bundle_pressure_inventory": pressure_inventory,
        "raw_source_backlog": slice_payload["known_raw_source_backlog"],
        "slice_summary": slice_payload["summary"],
    }
    summary_text = _build_summary_text(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(summary_text + "\n", encoding="utf-8")
    return {
        "summary": payload["summary"],
        "artifact_path": str(artifact_path),
        "summary_path": str(summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build diagnostics for broader AU corpus coverage across persisted real bundles.")
    parser.add_argument("--bundle-path", action="append", default=[], help="Real workbench bundle path; repeat to override the default set.")
    parser.add_argument("--raw-source-root", default=str(DEFAULT_RAW_SOURCE_ROOT), help="Directory containing known raw transcript source files.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write diagnostics into.")
    args = parser.parse_args()

    result = build_diagnostics(
        Path(args.output_dir).resolve(),
        bundle_paths=_collect_paths(args.bundle_path),
        raw_source_root=_coerce_path(args.raw_source_root),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
