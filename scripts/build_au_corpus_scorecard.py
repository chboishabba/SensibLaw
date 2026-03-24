#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
ARTIFACT_VERSION = "au_corpus_scorecard_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
DEFAULT_BUNDLE_PATHS = [
    REPO_ROOT / "itir-svelte" / "tests" / "fixtures" / "fact_review_wave1_real_au_demo_bundle.json",
    REPO_ROOT / "itir-svelte" / "tests" / "fixtures" / "fact_review_wave3_real_fragmented_support_demo_bundle.json",
    REPO_ROOT / "itir-svelte" / "tests" / "fixtures" / "fact_review_wave5_real_professional_handoff_demo_bundle.json",
    REPO_ROOT / "itir-svelte" / "tests" / "fixtures" / "fact_review_wave5_real_false_coherence_demo_bundle.json",
]
DEFAULT_RAW_SOURCE_ROOT = REPO_ROOT / "SensibLaw" / "demo" / "ingest" / "hca_case_s942025" / "media" / "transcripts"


def _coerce_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _collect_paths(values: Iterable[str]) -> list[Path]:
    paths = [_coerce_path(str(value)) for value in values]
    if not paths:
        return [path.resolve() for path in DEFAULT_BUNDLE_PATHS]
    return paths


def _load_workbench(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("selector", {}), payload["workbench"]


def _sum_field(rows: Iterable[dict[str, Any]], field: str) -> int:
    total = 0
    for row in rows:
        value = row.get(field)
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def _build_slice(bundle_paths: list[Path], *, raw_source_root: Path) -> dict[str, Any]:
    bundle_rows: list[dict[str, Any]] = []
    workflow_kinds: set[str] = set()
    source_labels: set[str] = set()
    workflow_run_ids: set[str] = set()

    for path in bundle_paths:
        selector, workbench = _load_workbench(path)
        summary = workbench.get("summary", {}) if isinstance(workbench.get("summary"), dict) else {}
        workflow_kind = str(selector.get("workflow_kind") or "")
        source_label = str(selector.get("source_label") or "")
        workflow_run_id = str(selector.get("workflow_run_id") or "")
        if workflow_kind:
            workflow_kinds.add(workflow_kind)
        if source_label:
            source_labels.add(source_label)
        if workflow_run_id:
            workflow_run_ids.add(workflow_run_id)
        bundle_rows.append(
            {
                "bundle_path": str(path.relative_to(REPO_ROOT)),
                "workflow_kind": workflow_kind,
                "workflow_run_id": workflow_run_id,
                "source_label": source_label,
                "source_count": int(summary.get("source_count") or 0),
                "statement_count": int(summary.get("statement_count") or 0),
                "observation_count": int(summary.get("observation_count") or 0),
                "fact_count": int(summary.get("fact_count") or 0),
                "event_count": int(summary.get("event_count") or 0),
                "review_queue_count": int(summary.get("review_queue_count") or 0),
                "contested_item_count": int(summary.get("contested_item_count") or 0),
                "approximate_event_count": int(summary.get("approximate_event_count") or 0),
            }
        )

    raw_files = sorted(path for path in raw_source_root.glob("*") if path.is_file()) if raw_source_root.exists() else []
    raw_files_by_suffix: dict[str, int] = {}
    for path in raw_files:
        suffix = path.suffix or "<none>"
        raw_files_by_suffix[suffix] = raw_files_by_suffix.get(suffix, 0) + 1

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "real_bundle_coverage_scorecard",
        "summary": {
            "included_real_bundle_count": len(bundle_rows),
            "workflow_kind_count": len(workflow_kinds),
            "source_label_count": len(source_labels),
            "workflow_run_count": len(workflow_run_ids),
            "source_count_total": _sum_field(bundle_rows, "source_count"),
            "statement_count_total": _sum_field(bundle_rows, "statement_count"),
            "observation_count_total": _sum_field(bundle_rows, "observation_count"),
            "fact_count_total": _sum_field(bundle_rows, "fact_count"),
            "event_count_total": _sum_field(bundle_rows, "event_count"),
            "review_queue_count_total": _sum_field(bundle_rows, "review_queue_count"),
            "contested_item_count_total": _sum_field(bundle_rows, "contested_item_count"),
            "approximate_event_count_total": _sum_field(bundle_rows, "approximate_event_count"),
            "known_raw_transcript_file_count": len(raw_files),
        },
        "included_workflow_kinds": sorted(workflow_kinds),
        "included_source_labels": sorted(source_labels),
        "bundle_inventory": bundle_rows,
        "known_raw_source_backlog": {
            "root": str(raw_source_root.relative_to(REPO_ROOT)) if raw_source_root.exists() else str(raw_source_root),
            "file_count": len(raw_files),
            "files_by_suffix": raw_files_by_suffix,
            "files": [str(path.relative_to(REPO_ROOT)) for path in raw_files],
        },
    }


def _build_summary_text(slice_payload: dict[str, Any]) -> str:
    summary = slice_payload["summary"]
    lines = [
        "# AU Corpus Scorecard Summary",
        "",
        "This artifact moves the AU lane one step past the bounded handoff",
        "checkpoint. It counts what is currently covered by persisted real",
        "workbench bundles, and it keeps known raw transcript material visible",
        "when it is not yet represented in that bundle set.",
        "",
        "## Current real-bundle coverage",
        "",
        f"- Included real bundles: {summary['included_real_bundle_count']}",
        f"- Workflow kinds: {', '.join(slice_payload.get('included_workflow_kinds', [])) or 'none'}",
        f"- Source labels: {summary['source_label_count']}",
        f"- Statements: {summary['statement_count_total']}",
        f"- Observations: {summary['observation_count_total']}",
        f"- Facts: {summary['fact_count_total']}",
        f"- Events: {summary['event_count_total']}",
        f"- Review queue items: {summary['review_queue_count_total']}",
        f"- Contested items: {summary['contested_item_count_total']}",
        f"- Approximate events: {summary['approximate_event_count_total']}",
        "",
        "## Bundle inventory",
        "",
    ]
    for row in slice_payload["bundle_inventory"]:
        lines.append(
            f"- {row['source_label']} ({row['workflow_kind']}): "
            f"{row['fact_count']} facts, {row['observation_count']} observations, "
            f"{row['event_count']} events, {row['review_queue_count']} review items."
        )
    backlog = slice_payload["known_raw_source_backlog"]
    lines.extend(
        [
            "",
            "## Known raw-source backlog",
            "",
            f"- Raw transcript files currently present under `{backlog['root']}`: {backlog['file_count']}",
            f"- File suffix breakdown: {json.dumps(backlog['files_by_suffix'], sort_keys=True)}",
            "",
            "## Reading",
            "",
            "- This is still a checkpoint, not a completeness proof over every AU",
            "  source family we may ultimately care about.",
            "- It is, however, materially stronger than reading the current 3-fact",
            "  AU handoff slice as if it were the whole corpus.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_scorecard(slice_payload: dict[str, Any]) -> dict[str, Any]:
    summary = slice_payload["summary"]
    return {
        "destination": "broader_au_corpus_understanding",
        "current_stage": "real_bundle_coverage_checkpoint",
        "included_real_bundle_count": summary["included_real_bundle_count"],
        "workflow_kind_count": summary["workflow_kind_count"],
        "source_label_count": summary["source_label_count"],
        "workflow_run_count": summary["workflow_run_count"],
        "source_count_total": summary["source_count_total"],
        "statement_count_total": summary["statement_count_total"],
        "observation_count_total": summary["observation_count_total"],
        "fact_count_total": summary["fact_count_total"],
        "event_count_total": summary["event_count_total"],
        "review_queue_count_total": summary["review_queue_count_total"],
        "contested_item_count_total": summary["contested_item_count_total"],
        "approximate_event_count_total": summary["approximate_event_count_total"],
        "known_raw_transcript_file_count": summary["known_raw_transcript_file_count"],
    }


def build_corpus_scorecard(output_dir: Path, *, bundle_paths: list[Path] | None = None, raw_source_root: Path = DEFAULT_RAW_SOURCE_ROOT) -> dict[str, Any]:
    selected_bundle_paths = [path.resolve() for path in (bundle_paths or DEFAULT_BUNDLE_PATHS)]
    slice_payload = _build_slice(selected_bundle_paths, raw_source_root=raw_source_root.resolve())
    summary_text = _build_summary_text(slice_payload)
    scorecard_payload = _build_scorecard(slice_payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "slice_path": output_dir / f"{ARTIFACT_VERSION}.json",
        "summary_path": output_dir / f"{ARTIFACT_VERSION}.summary.md",
    }
    paths["slice_path"].write_text(json.dumps(scorecard_payload | {"slice": slice_payload}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["summary_path"].write_text(summary_text + "\n", encoding="utf-8")
    return {
        "scorecard": scorecard_payload,
        **{k: str(v) for k, v in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the broader AU corpus scorecard from persisted real workbench bundles.")
    parser.add_argument("--bundle-path", action="append", default=[], help="Real workbench bundle path; repeat to override the default set.")
    parser.add_argument("--raw-source-root", default=str(DEFAULT_RAW_SOURCE_ROOT), help="Directory containing known raw transcript source files.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the AU corpus scorecard into.")
    args = parser.parse_args()

    bundle_paths = _collect_paths(args.bundle_path)
    payload = build_corpus_scorecard(
        Path(args.output_dir).resolve(),
        bundle_paths=bundle_paths,
        raw_source_root=_coerce_path(args.raw_source_root),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
