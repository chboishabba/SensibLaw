#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
ARTIFACT_VERSION = "au_public_handoff_v1"
SOURCE_BUNDLE_PATH = (
    REPO_ROOT / "itir-svelte" / "tests" / "fixtures" / "fact_review_wave1_real_au_demo_bundle.json"
)
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION

import sys

if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from src.zelph_bridge import run_zelph_inference


def _sanitize_id(raw: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_").lower()


def _load_workbench(source_bundle_path: Path) -> dict[str, Any]:
    payload = json.loads(source_bundle_path.read_text(encoding="utf-8"))
    return payload["workbench"]


def _coerce_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _collect_sources(sources: Iterable[str]) -> list[Path]:
    paths = list(_coerce_path(str(src)) for src in sources)
    if not paths:
        return [SOURCE_BUNDLE_PATH.resolve()]
    return paths


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def _merge_summary_values(summaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for summary in summaries:
        for key, value in summary.items():
            if isinstance(value, (int, float)):
                merged[key] = float(merged.get(key, 0)) + float(value)
    for key in list(merged.keys()):
        if merged[key].is_integer():
            merged[key] = int(merged[key])
    merged["merged_source_bundle_count"] = len(list(summaries))
    return merged


def _build_slice(workbench_by_source: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    review_fact_ids = {
        str(row.get("fact_id") or "")
        for _source_label, workbench in workbench_by_source
        for row in workbench.get("review_queue", [])
    }

    selected_facts = []
    selected_rows: dict[str, dict[str, Any]] = {}

    for source_label, workbench in workbench_by_source:
        for row in workbench.get("facts", []):
            fact_id = str(row.get("fact_id") or "")
            fact_text = _normalize_text(row.get("fact_text")) or _normalize_text(row.get("canonical_label"))
            row_key = fact_text or fact_id
            merged = selected_rows.get(row_key)
            if merged is None:
                merged = {
                    "fact_id": fact_id,
                    "fact_text": fact_text,
                    "source_types": list(dict.fromkeys(row.get("source_types", []))),
                    "signal_classes": list(dict.fromkeys(row.get("signal_classes", []))),
                    "legal_procedural_predicates": list(dict.fromkeys(row.get("legal_procedural_predicates", []))),
                    "source_bundles": [source_label],
                }
                selected_rows[row_key] = merged
                continue

            merged["source_bundles"] = sorted(set(merged.get("source_bundles", []) + [source_label]))
            for field in ("source_types", "signal_classes", "legal_procedural_predicates"):
                merged[field] = list(dict.fromkeys(list(merged.get(field, [])) + list(row.get(field, []))))

    for row in selected_rows.values():
        selected_facts.append(
            {
                "fact_id": row["fact_id"],
                "fact_text": row["fact_text"],
                "source_types": row["source_types"],
                "signal_classes": row["signal_classes"],
                "legal_procedural_predicates": row["legal_procedural_predicates"],
                "source_bundles": row["source_bundles"],
                "review_status": "review_queue" if row["fact_id"] in review_fact_ids else "captured",
            }
        )

    summaries = [wb.get("summary", {}) for _, wb in workbench_by_source if isinstance(wb.get("summary"), dict)]
    merged_summary = _merge_summary_values(summaries) if summaries else {}
    source_labels = [source_label for source_label, _ in workbench_by_source]

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "real_checked_bundle_projection",
        "source_bundle_paths": source_labels,
        "run": workbench_by_source[0][1].get("run", {}),
        "summary": merged_summary,
        "selected_facts": selected_facts,
        "review_queue_fact_ids": sorted(fid for fid in review_fact_ids if fid),
        "operator_view_names": sorted(
            set(
                name
                for _, workbench in workbench_by_source
                for name in workbench.get("operator_views", {}).keys()
            )
        ),
        "chronology_summary": workbench_by_source[0][1].get("chronology_summary", {}),
        "contested_summary": workbench_by_source[0][1].get("contested_summary", {}),
    }


def _build_summary_text(slice_payload: dict[str, Any]) -> str:
    summary = slice_payload["summary"]
    source_count = len(slice_payload.get("source_bundle_paths", []))
    source_note = ""
    if source_count > 1:
        source_note = f"Source bundles: {source_count} real workbench bundles included. "
    lines = [
        "# AU Public Handoff Narrative Summary",
        "",
        "This checked AU handoff artifact is built from the current real AU",
        "procedural workbench bundle. It is meant to explain, in prose, what the",
        "system currently understands and what it still keeps under review.",
        "",
        source_note,
        "",
        "## What the system recovered from the current AU slice",
        "",
    ]
    for row in slice_payload["selected_facts"]:
        lines.append(f"- {row['fact_text']}")
    lines.extend(
        [
            "",
            "## What the workbench says about this slice",
            "",
        f"- Facts: {summary.get('fact_count', len(slice_payload.get('selected_facts', [])))}",
        f"- Observations: {summary.get('observation_count', 0)}",
        f"- Events: {summary.get('event_count', 0)}",
            f"- Review queue items: {summary.get('review_queue_count', 0)}",
            f"- Contested items: {summary.get('contested_item_count', 0)}",
            f"- Approximate events: {summary.get('approximate_event_count', 0)}",
            "",
            "## Why this matters for Zelph",
            "",
            "- It shows that a real AU procedural slice can already be exported as",
            "  structured facts with legal-procedural signal classes.",
            "- It exposes both captured procedural understanding and the review queue,",
            "  rather than pretending the bundle is already fully settled.",
            "- It is the AU counterpart to the checked GWB public handoff shape.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_facts(slice_payload: dict[str, Any]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for row in slice_payload["selected_facts"]:
        fact_id = f"fact_{_sanitize_id(row['fact_id'])}"
        for line in (
            f'{fact_id} "kind" "fact"',
            f'{fact_id} "label" "{row["fact_text"]}"',
            f'{fact_id} "canonical_key" "{row["fact_id"]}"',
            f'{fact_id} "review_status" "{row["review_status"]}"',
        ):
            if line not in seen:
                seen.add(line)
                lines.append(line)
        for value in row.get("source_types", []):
            line = f'{fact_id} "source_type" "{value}"'
            if line not in seen:
                seen.add(line)
                lines.append(line)
        for value in row.get("signal_classes", []):
            line = f'{fact_id} "signal_class" "{value}"'
            if line not in seen:
                seen.add(line)
                lines.append(line)
        for value in row.get("source_bundles", []):
            line = f'{fact_id} "source_bundle" "{value}"'
            if line not in seen:
                seen.add(line)
                lines.append(line)
        for value in row.get("legal_procedural_predicates", []):
            line = f'{fact_id} "legal_procedural_predicate" "{value}"'
            if line not in seen:
                seen.add(line)
                lines.append(line)
    return "\n".join(lines) + "\n"


def _build_rules() -> str:
    return (
        "# AU public handoff rules\n\n"
        '(X "signal_class" "procedural_outcome") => (X "au_procedural_fact" "true")\n'
        '(X "signal_class" "appeal_stage_signal") => (X "au_procedural_fact" "true")\n'
        '(X "review_status" "review_queue") => (X "needs_review_due_to_procedural_pressure" "true")\n\n'
        'X "au_procedural_fact" "true"\n'
        'X "needs_review_due_to_procedural_pressure" "true"\n'
    )


def _build_scorecard(slice_payload: dict[str, Any], engine_status: str | None) -> dict[str, Any]:
    summary = slice_payload["summary"]
    return {
        "destination": "complete_au_topic_understanding",
        "current_stage": "checked_real_workbench_checkpoint",
        "fact_count": summary.get("fact_count", 0),
        "observation_count": summary.get("observation_count", 0),
        "event_count": summary.get("event_count", 0),
        "review_queue_count": summary.get("review_queue_count", 0),
        "contested_item_count": summary.get("contested_item_count", 0),
        "approximate_event_count": summary.get("approximate_event_count", 0),
        "operator_view_count": len(slice_payload.get("operator_view_names", [])),
        "zelph_engine_status": engine_status or "unknown",
    }


def build_handoff_artifact(output_dir: Path, source_bundle_paths: list[Path] | None = None) -> dict[str, Any]:
    source_paths = _collect_sources(source_bundle_paths or [])
    workbench_by_source: list[tuple[str, dict[str, Any]]] = []
    for path in source_paths:
        workbench_by_source.append((str(path.relative_to(REPO_ROOT)), _load_workbench(path)))

    slice_payload = _build_slice(workbench_by_source)
    summary_text = _build_summary_text(slice_payload)
    facts_text = _build_facts(slice_payload)
    rules_text = _build_rules()
    engine_payload = run_zelph_inference(facts_text, rules_text)
    scorecard_payload = _build_scorecard(slice_payload, str(engine_payload.get("status") or "unknown"))

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "slice_path": output_dir / f"{ARTIFACT_VERSION}.slice.json",
        "summary_path": output_dir / f"{ARTIFACT_VERSION}.summary.md",
        "facts_path": output_dir / f"{ARTIFACT_VERSION}.facts.zlp",
        "rules_path": output_dir / f"{ARTIFACT_VERSION}.rules.zlp",
        "engine_path": output_dir / f"{ARTIFACT_VERSION}.engine.json",
        "scorecard_path": output_dir / f"{ARTIFACT_VERSION}.scorecard.json",
    }
    paths["slice_path"].write_text(json.dumps(slice_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["summary_path"].write_text(summary_text, encoding="utf-8")
    paths["facts_path"].write_text(facts_text, encoding="utf-8")
    paths["rules_path"].write_text(rules_text, encoding="utf-8")
    paths["engine_path"].write_text(json.dumps(engine_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["scorecard_path"].write_text(json.dumps(scorecard_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "engine_status": engine_payload.get("status"),
        "scorecard": scorecard_payload,
        "summary": slice_payload["summary"],
        **{k: str(v) for k, v in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the checked AU procedural Zelph handoff artifact.")
    parser.add_argument(
        "--source-bundle",
        action="append",
        default=[],
        help="Workbench bundle path; repeat for multi-source merged artifacts.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the checked handoff artifact into.")
    args = parser.parse_args()
    print(
        json.dumps(
            build_handoff_artifact(
                Path(args.output_dir).resolve(),
                source_bundle_paths=[_coerce_path(path) for path in args.source_bundle],
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
