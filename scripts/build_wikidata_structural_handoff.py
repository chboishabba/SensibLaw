#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.storage.repo_roots import repo_root, sensiblaw_root

REPO_ROOT = repo_root()
SENSIBLAW_ROOT = sensiblaw_root()
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from src.ontology.wikidata_disjointness import project_wikidata_disjointness_payload
from src.ontology.wikidata_hotspot import generate_hotspot_cluster_pack, load_hotspot_manifest
from src.policy.wikidata_structural_io import load_json_object, relative_repo_path
from src.zelph_bridge import run_zelph_inference


ARTIFACT_VERSION = "wikidata_structural_handoff_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
HOTSPOT_MANIFEST_PATH = REPO_ROOT / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
QUALIFIER_BASELINE_PATH = SENSIBLAW_ROOT / "tests" / "fixtures" / "wikidata" / "real_qualifier_imported_slice_20260307.json"
QUALIFIER_DRIFT_SLICE_PATH = (
    SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "wikidata"
    / "q100104196_p166_2277985537_2277985693"
    / "slice.json"
)
QUALIFIER_DRIFT_PROJECTION_PATH = (
    SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "wikidata"
    / "q100104196_p166_2277985537_2277985693"
    / "projection.json"
)
DISJOINTNESS_CASE_PATHS = {
    "nucleon_baseline": SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_nucleon_real_pack_v1"
    / "slice.json",
    "fixed_construction_contradiction": SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_fixed_construction_real_pack_v1"
    / "slice.json",
    "working_fluid_contradiction": SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_working_fluid_real_pack_v1"
    / "slice.json",
}
HOTSPOT_PACK_IDS = (
    "mixed_order_live_pack_v1",
    "p279_scc_live_pack_v1",
    "qualifier_drift_p166_live_pack_v1",
    "software_entity_kind_collapse_pack_v0",
)


def _sanitize_id(raw: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_").lower()


def _quote(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _relative(path: Path) -> str:
    return relative_repo_path(path, repo_root=REPO_ROOT)


def _build_qualifier_core() -> dict[str, Any]:
    baseline_payload = load_json_object(QUALIFIER_BASELINE_PATH)
    baseline_windows = baseline_payload.get("windows", [])
    statement_count = sum(
        len(window.get("statement_bundles", []))
        for window in baseline_windows
        if isinstance(window, dict)
    )
    property_pids = sorted(
        {
            str(bundle.get("property"))
            for window in baseline_windows
            if isinstance(window, dict)
            for bundle in window.get("statement_bundles", [])
            if isinstance(bundle, dict) and bundle.get("property") is not None
        }
    )
    drift_projection = load_json_object(QUALIFIER_DRIFT_PROJECTION_PATH)
    drift_rows = drift_projection.get("qualifier_drift", [])
    drift_row = drift_rows[0] if drift_rows else {}
    return {
        "baseline": {
            "source_path": _relative(QUALIFIER_BASELINE_PATH),
            "window_count": len(baseline_windows),
            "statement_count": statement_count,
            "property_pids": property_pids,
            "interpretation": "real importer-backed qualifier-bearing baseline with zero detected drift",
        },
        "drift_case": {
            "source_slice_path": _relative(QUALIFIER_DRIFT_SLICE_PATH),
            "projection_path": _relative(QUALIFIER_DRIFT_PROJECTION_PATH),
            "slot_id": drift_row.get("slot_id"),
            "subject_qid": drift_row.get("subject_qid"),
            "property_pid": drift_row.get("property_pid"),
            "severity": drift_row.get("severity"),
            "from_window": drift_row.get("from_window"),
            "to_window": drift_row.get("to_window"),
            "qualifier_property_set_t1": drift_row.get("qualifier_property_set_t1", []),
            "qualifier_property_set_t2": drift_row.get("qualifier_property_set_t2", []),
            "qualifier_signatures_t1": drift_row.get("qualifier_signatures_t1", []),
            "qualifier_signatures_t2": drift_row.get("qualifier_signatures_t2", []),
            "interpretation": "repo-pinned real drift case with persisted projection and medium severity",
        },
    }


def _build_hotspot_governance() -> dict[str, Any]:
    manifest = load_hotspot_manifest(HOTSPOT_MANIFEST_PATH)
    cluster_pack = generate_hotspot_cluster_pack(
        manifest,
        repo_root=REPO_ROOT,
        pack_ids=HOTSPOT_PACK_IDS,
    )
    packs = []
    for pack in cluster_pack.get("packs", []):
        clusters = pack.get("clusters", [])
        sample_questions = []
        for cluster in clusters[:2]:
            questions = cluster.get("questions", [])
            if questions:
                sample_questions.append(questions[0].get("text"))
        packs.append(
            {
                "pack_id": pack.get("pack_id"),
                "hotspot_family": pack.get("hotspot_family"),
                "promotion_status": pack.get("promotion_status"),
                "hold_reason": pack.get("hold_reason"),
                "cluster_count": pack.get("cluster_count"),
                "primary_story": pack.get("primary_story"),
                "sample_questions": sample_questions,
                "source_artifacts": pack.get("source_artifacts", []),
            }
        )
    return {
        "manifest_path": _relative(HOTSPOT_MANIFEST_PATH),
        "selected_pack_ids": list(cluster_pack.get("selected_pack_ids", [])),
        "pack_count": cluster_pack.get("pack_count", 0),
        "cluster_count": cluster_pack.get("cluster_count", 0),
        "packs": packs,
    }


def _case_status(report: dict[str, Any]) -> str:
    review = report.get("review_summary", {})
    subclass_count = int(review.get("subclass_violation_count") or 0)
    instance_count = int(review.get("instance_violation_count") or 0)
    if subclass_count == 0 and instance_count == 0:
        return "baseline"
    return "contradiction"


def _build_disjointness_cases() -> list[dict[str, Any]]:
    cases = []
    for case_id, path in DISJOINTNESS_CASE_PATHS.items():
        payload = load_json_object(path)
        report = project_wikidata_disjointness_payload(payload)
        metadata = payload.get("metadata", {})
        review = report.get("review_summary", {})
        pair_labels = [
            f"{row.get('left_label')} vs {row.get('right_label')}"
            for row in report.get("disjoint_pairs", [])
        ]
        cases.append(
            {
                "case_id": case_id,
                "source_path": _relative(path),
                "source_note": metadata.get("source_note"),
                "case_status": _case_status(report),
                "pair_labels": pair_labels,
                "disjoint_pair_count": review.get("disjoint_pair_count", 0),
                "subclass_violation_count": review.get("subclass_violation_count", 0),
                "instance_violation_count": review.get("instance_violation_count", 0),
                "culprit_class_count": review.get("culprit_class_count", 0),
                "culprit_item_count": review.get("culprit_item_count", 0),
            }
        )
    return cases


def _build_slice() -> dict[str, Any]:
    qualifier_core = _build_qualifier_core()
    hotspot_governance = _build_hotspot_governance()
    disjointness_cases = _build_disjointness_cases()

    promoted_pack_count = sum(
        1 for pack in hotspot_governance["packs"] if pack.get("promotion_status") == "promoted"
    )
    held_pack_count = sum(
        1 for pack in hotspot_governance["packs"] if pack.get("hold_reason")
    )
    contradiction_case_count = sum(
        1 for case in disjointness_cases if case.get("case_status") == "contradiction"
    )
    baseline_case_count = sum(
        1 for case in disjointness_cases if case.get("case_status") == "baseline"
    )

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "checked_structural_review_handoff",
        "summary": {
            "qualifier_baseline_statement_count": qualifier_core["baseline"]["statement_count"],
            "qualifier_drift_case_count": 1,
            "promoted_hotspot_pack_count": promoted_pack_count,
            "held_hotspot_pack_count": held_pack_count,
            "hotspot_cluster_count": hotspot_governance["cluster_count"],
            "disjointness_case_count": len(disjointness_cases),
            "contradiction_case_count": contradiction_case_count,
            "zero_violation_baseline_case_count": baseline_case_count,
        },
        "qualifier_core": qualifier_core,
        "hotspot_governance": hotspot_governance,
        "disjointness_cases": disjointness_cases,
    }


def _build_summary_text(slice_payload: dict[str, Any]) -> str:
    qualifier_core = slice_payload["qualifier_core"]
    hotspot = slice_payload["hotspot_governance"]
    disjointness_cases = slice_payload["disjointness_cases"]
    lines = [
        "# Wikidata Structural Handoff Narrative Summary",
        "",
        "This checked handoff artifact is a bounded wiki/Wikidata structural",
        "review slice. It is meant to show, in plain language, what the repo can",
        "already preserve and hand off from pinned structural diagnostics.",
        "",
        "## Qualifier core",
        "",
        (
            f"- The importer-backed baseline preserves "
            f"{qualifier_core['baseline']['statement_count']} qualifier-bearing statements "
            f"across {qualifier_core['baseline']['window_count']} windows for "
            f"{', '.join(qualifier_core['baseline']['property_pids'])} without surfacing drift."
        ),
        (
            f"- The pinned real drift case {qualifier_core['drift_case']['slot_id']} "
            f"remains checked at severity={qualifier_core['drift_case']['severity']} "
            f"from {qualifier_core['drift_case']['from_window']} to "
            f"{qualifier_core['drift_case']['to_window']}."
        ),
        "",
        "## Structural exemplars already ready for handoff",
        "",
    ]
    for pack in hotspot["packs"]:
        if pack["promotion_status"] != "promoted":
            continue
        lines.append(
            f"- {pack['pack_id']} ({pack['hotspot_family']}) is already promoted with "
            f"{pack['cluster_count']} generated clusters."
        )
    lines.extend(["", "## Structural review pressure kept explicit", ""])
    for pack in hotspot["packs"]:
        if pack["promotion_status"] == "promoted":
            continue
        lines.append(
            f"- {pack['pack_id']} remains held/promotable: "
            f"{pack['hold_reason']}."
        )
    lines.append("- GNU and GNU Project remain visible as review pressure rather than being over-promoted.")
    for case in disjointness_cases:
        pair_text = ", ".join(case["pair_labels"])
        if case["case_status"] == "baseline":
            lines.append(
                f"- {case['case_id']} is a zero-violation baseline for {pair_text}."
            )
        else:
            lines.append(
                f"- {case['case_id']} is a real contradiction case for {pair_text}: "
                f"subclass_violations={case['subclass_violation_count']}, "
                f"instance_violations={case['instance_violation_count']}."
            )
    lines.extend(
        [
            "",
            "## Why this matters",
            "",
            "- The handoff now has one human-readable checked slice instead of only scattered status notes.",
            "- It shows both checked structural exemplars and explicit review pressure.",
            "- It keeps the boundary clear: SensibLaw/ITIR diagnoses and preserves, while downstream reasoning stays bounded.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_facts(slice_payload: dict[str, Any]) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    def emit(line: str) -> None:
        if line not in seen:
            seen.add(line)
            lines.append(line)

    emit('qualifier_import_baseline "kind" "qualifier_baseline"')
    emit(
        f'qualifier_import_baseline "statement_count" {_quote(slice_payload["qualifier_core"]["baseline"]["statement_count"])}'
    )
    emit(
        f'qualifier_import_baseline "window_count" {_quote(slice_payload["qualifier_core"]["baseline"]["window_count"])}'
    )
    for pid in slice_payload["qualifier_core"]["baseline"]["property_pids"]:
        emit(f'qualifier_import_baseline "property_pid" {_quote(pid)}')

    drift = slice_payload["qualifier_core"]["drift_case"]
    emit('qualifier_drift_q100104196_p166 "kind" "qualifier_drift_case"')
    emit(f'qualifier_drift_q100104196_p166 "slot_id" {_quote(drift["slot_id"])}')
    emit(f'qualifier_drift_q100104196_p166 "severity" {_quote(drift["severity"])}')
    emit('qualifier_drift_q100104196_p166 "qualifier_drift" "true"')

    for pack in slice_payload["hotspot_governance"]["packs"]:
        node_id = f'pack_{_sanitize_id(str(pack["pack_id"]))}'
        emit(f'{node_id} "kind" "hotspot_pack"')
        emit(f'{node_id} "hotspot_family" {_quote(pack["hotspot_family"])}')
        emit(f'{node_id} "promotion_status" {_quote(pack["promotion_status"])}')
        emit(f'{node_id} "cluster_count" {_quote(pack["cluster_count"])}')
        if pack.get("hold_reason"):
            emit(f'{node_id} "hold_reason" {_quote(pack["hold_reason"])}')

    for case in slice_payload["disjointness_cases"]:
        node_id = f'case_{_sanitize_id(str(case["case_id"]))}'
        emit(f'{node_id} "kind" "disjointness_case"')
        emit(f'{node_id} "case_status" {_quote(case["case_status"])}')
        emit(
            f'{node_id} "subclass_violation_count" {_quote(case["subclass_violation_count"])}'
        )
        emit(
            f'{node_id} "instance_violation_count" {_quote(case["instance_violation_count"])}'
        )
        emit(f'{node_id} "culprit_class_count" {_quote(case["culprit_class_count"])}')
        emit(f'{node_id} "culprit_item_count" {_quote(case["culprit_item_count"])}')

    return "\n".join(lines) + "\n"


def _build_rules() -> str:
    return (
        "# Wikidata structural handoff rules\n\n"
        '(X "promotion_status" "promoted") => (X "structural_case_ready_for_handoff" "true")\n'
        '(X "case_status" "contradiction") => (X "needs_review_due_to_structure" "true")\n'
        '(X "hold_reason" Y) => (X "needs_review_due_to_governance" "true")\n'
        '(X "kind" "qualifier_baseline") => (X "demonstrates_import_preservation" "true")\n'
        '(X "kind" "qualifier_drift_case") => (X "structural_case_ready_for_handoff" "true")\n\n'
        'X "structural_case_ready_for_handoff" "true"\n'
        'X "needs_review_due_to_structure" "true"\n'
        'X "needs_review_due_to_governance" "true"\n'
        'X "demonstrates_import_preservation" "true"\n'
    )


def _build_scorecard(slice_payload: dict[str, Any], engine_status: str | None) -> dict[str, Any]:
    summary = slice_payload["summary"]
    return {
        "destination": "checked_wikidata_structural_understanding",
        "current_stage": "checked_structural_handoff_checkpoint",
        "promoted_hotspot_pack_count": summary["promoted_hotspot_pack_count"],
        "held_hotspot_pack_count": summary["held_hotspot_pack_count"],
        "hotspot_cluster_count": summary["hotspot_cluster_count"],
        "disjointness_case_count": summary["disjointness_case_count"],
        "contradiction_case_count": summary["contradiction_case_count"],
        "zero_violation_baseline_case_count": summary["zero_violation_baseline_case_count"],
        "qualifier_baseline_statement_count": summary["qualifier_baseline_statement_count"],
        "qualifier_drift_case_count": summary["qualifier_drift_case_count"],
        "zelph_engine_status": engine_status or "unknown",
    }


def build_handoff_artifact(output_dir: Path) -> dict[str, Any]:
    slice_payload = _build_slice()
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
        **{key: str(value) for key, value in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the checked wiki/Wikidata structural handoff artifact.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the checked handoff artifact into.")
    args = parser.parse_args()
    print(json.dumps(build_handoff_artifact(Path(args.output_dir).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
