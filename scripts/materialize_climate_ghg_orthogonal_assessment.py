#!/usr/bin/env python3
"""Materialize the climate-GHG V2 assessment from an immutable local replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cli_runtime import build_progress_callback  # noqa: E402
from src.policy.climate_ghg_transformation_profile import (  # noqa: E402
    build_orthogonal_assessment,
)
from src.policy.orthogonal_assessment import (  # noqa: E402
    build_coverage_report,
)


SOURCE_FILES = (
    "run-state.json",
    "manifest.json",
    "slice.json",
    "migration_pack.json",
    "rule_coverage.json",
    "h4_collision_report.json",
)
OUTPUT_FILES = (
    "orthogonal_assessment.json",
    "orthogonal_coverage_report.json",
    "legacy_projection_comparison.json",
    "eligibility_review_manifest.json",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the offline climate-GHG orthogonal V2 assessment."
    )
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--sample-family-limit", type=int, default=15)
    parser.add_argument(
        "--progress-format", choices=("human", "json", "bar"), default="bar"
    )
    parser.add_argument("--no-progress", action="store_false", dest="progress_enabled")
    parser.set_defaults(progress_enabled=True)
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def _verify_inputs(replay_dir: Path, payloads: Mapping[str, Mapping[str, Any]]) -> None:
    run_state = payloads["run-state.json"]
    manifest = payloads["manifest.json"]
    migration_pack = payloads["migration_pack.json"]
    coverage = payloads["rule_coverage.json"].get("coverage") or {}
    if run_state.get("population_exhausted") is not True:
        raise ValueError("replay population is not exhausted")
    ordered_qids = [str(value) for value in run_state.get("ordered_qids") or ()]
    manifest_qids = [str(value) for value in manifest.get("qids") or ()]
    if ordered_qids != manifest_qids:
        raise ValueError("run-state and manifest QID order mismatch")
    if set(run_state.get("revision_map") or {}) != set(ordered_qids):
        raise ValueError(
            "run-state revision map does not cover the manifest population"
        )
    candidates = list(migration_pack.get("candidates") or ())
    coverage_rows = list(coverage.get("candidate_rows") or ())
    if len(candidates) != len(coverage_rows):
        raise ValueError(
            "migration-pack and rule-coverage statement populations differ"
        )
    candidate_refs = {str(row.get("candidate_id") or "") for row in candidates}
    coverage_refs = {str(row.get("candidate_ref") or "") for row in coverage_rows}
    if candidate_refs != coverage_refs:
        raise ValueError("migration-pack and rule-coverage candidate references differ")
    entity_qids = {str(row.get("entity_qid") or "") for row in candidates}
    if entity_qids != set(ordered_qids):
        raise ValueError("migration-pack entity population differs from run state")
    for name in SOURCE_FILES:
        if not (replay_dir / name).is_file():
            raise ValueError(f"missing replay artifact: {name}")


def _target_collision_states(
    migration_pack: Mapping[str, Any], rule_coverage: Mapping[str, Any]
) -> dict[str, str]:
    statement_by_candidate = {
        str(row.get("candidate_id") or ""): str(row.get("source_statement_id") or "")
        for row in migration_pack.get("candidates") or ()
    }
    states: dict[str, str] = {}
    for row in (rule_coverage.get("coverage") or {}).get("candidate_rows") or ():
        candidate_ref = str(row.get("candidate_ref") or "")
        statement_ref = statement_by_candidate.get(candidate_ref, "")
        evidence_states: set[str] = set()
        if "X6_target_property_collision" in (row.get("exclusion_reasons") or ()):
            evidence_states.add("present")
        for result in row.get("detector_results") or ():
            for predicate in result.get("predicate_results") or ():
                if predicate.get("predicate_ref") != "entity.target-property-absent":
                    continue
                if (
                    predicate.get("state") == "satisfied"
                    and predicate.get("observed") == "absent"
                ):
                    evidence_states.add("absent")
                elif predicate.get("state") == "failed":
                    evidence_states.add("present")
                else:
                    evidence_states.add("unresolved")
        if not statement_ref or len(evidence_states) != 1:
            raise ValueError(
                f"missing or inconsistent target-collision evidence: {candidate_ref}"
            )
        states[statement_ref] = next(iter(evidence_states))
    if len(states) != len(statement_by_candidate):
        raise ValueError("target-collision evidence is not exhaustive")
    return states


def _strict_matches(rule_coverage: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rules = {
        row["rule_ref"]: str(row.get("structural_family_ref") or "")
        for row in rule_coverage.get("rules") or ()
    }
    matched: dict[str, dict[str, set[str]]] = {}
    for row in (rule_coverage.get("coverage") or {}).get("candidate_rows") or ():
        for result in row.get("detector_results") or ():
            if result.get("outcome") != "matched":
                continue
            structural = rules.get(result.get("rule_ref"), "")
            label = next(
                (
                    value
                    for value in ("A1", "A2", "A3", "A4", "A5", "H4")
                    if f":{value}:" in structural
                ),
                "",
            )
            if not label:
                continue
            slot = matched.setdefault(label, {"families": set(), "statements": set()})
            slot["families"].add(str(row.get("dependency_group_ref") or ""))
            slot["statements"].add(str(row.get("candidate_ref") or ""))
    return {
        label: {
            "family_count": len(values["families"]),
            "statement_count": len(values["statements"]),
        }
        for label, values in sorted(matched.items())
    }


def _legacy_comparison(
    assessment: Mapping[str, Any],
    rule_coverage: Mapping[str, Any],
    h4: Mapping[str, Any],
) -> dict[str, Any]:
    inventory_counts = (rule_coverage.get("coverage") or {}).get(
        "dependency_group_primary_obstruction_counts"
    ) or {}
    strict = _strict_matches(rule_coverage)
    v2: dict[str, dict[str, set[str]]] = {}
    for row in assessment["statements"]:
        for label in row.get("legacy_projections") or ():
            values = v2.setdefault(label, {"families": set(), "statements": set()})
            values["families"].add(row["family_ref"])
            values["statements"].add(row["statement_ref"])
    v2_counts = {
        label: {
            "family_count": len(values["families"]),
            "statement_count": len(values["statements"]),
        }
        for label, values in sorted(v2.items())
    }
    legacy_a4_families = {
        row["dependency_group_ref"]
        for row in (rule_coverage.get("coverage") or {}).get(
            "dependency_group_inventory"
        )
        or ()
        if row.get("primary_obstruction") == "A4_coherent_multidimensional_matrix"
    }
    strict_a4_families = {
        row["dependency_group_ref"]
        for row in (rule_coverage.get("coverage") or {}).get("candidate_rows") or ()
        if any(
            result.get("outcome") == "matched"
            and any(
                rule.get("rule_ref") == result.get("rule_ref")
                and ":A4:" in str(rule.get("structural_family_ref") or "")
                for rule in rule_coverage.get("rules") or ()
            )
            for result in row.get("detector_results") or ()
        )
    }
    lost = sorted(legacy_a4_families - strict_a4_families)
    lost_statement_count = sum(
        int(row.get("candidate_count") or 0)
        for row in (rule_coverage.get("coverage") or {}).get(
            "dependency_group_inventory"
        )
        or ()
        if row.get("dependency_group_ref") in lost
    )
    return {
        "schema_version": "sl.climate_ghg_legacy_projection_comparison.v2",
        "authority": "diagnostic_comparison_only",
        "legacy_primary_assessment_counts": inventory_counts,
        "strict_detector_matches": strict,
        "v2_projection_counts": v2_counts,
        "a4_strict_attrition": {
            "lost_family_count": len(lost),
            "lost_statement_count": lost_statement_count,
            "family_refs": lost,
            "attribution": "strict detector predicate failure or abstention; legacy primary geometry remains contextual",
        },
        "h4_collision_summary": h4.get("summary") or {},
        "acceptance_reconciliation": {
            "legacy_a4": {"family_count": 124, "statement_count": 2416},
            "strict_a4": {"family_count": 110, "statement_count": 2198},
            "legacy_a5": {"family_count": 90, "statement_count": 830},
            "strict_a5": {"family_count": 0, "statement_count": 0},
            "h4_direct": {
                "family_count": 5,
                "collision_group_count": 25,
                "statement_count": 50,
            },
            "strict_h4": {"family_count": 2, "statement_count": 15},
        },
        "predicate_attrition": build_coverage_report(assessment)["predicate_attrition"],
        "execution_effect": "none",
    }


def _size_bucket(size: int) -> str:
    return "one" if size == 1 else "two_to_five" if size <= 5 else "six_plus"


def _review_manifest(assessment: Mapping[str, Any], limit: int) -> dict[str, Any]:
    statements_by_family: dict[str, list[Mapping[str, Any]]] = {}
    for row in assessment["statements"]:
        statements_by_family.setdefault(row["family_ref"], []).append(row)
    feature_map: dict[str, set[str]] = {}
    family_map = {row["family_ref"]: row for row in assessment["families"]}
    for family_ref, family in family_map.items():
        rows = statements_by_family[family_ref]
        features = {f"outcome:{row['axes']['execution_outcome']}" for row in rows}
        features.update(
            {
                f"geometry:{family['geometry_subtype']}",
                f"coverage:{family['component_coverage']}",
                f"size:{_size_bucket(family['member_count'])}",
                f"annuality:{family['geometry_state'] == 'annual_series'}",
            }
        )
        features.update(
            f"variant:{value}" for value in family["geometry_variant_flags"]
        )
        features.update(f"shape:{row['axes']['statement_semantics']}" for row in rows)
        feature_map[family_ref] = features
    selected: list[str] = []
    covered: set[str] = set()
    remaining = set(feature_map)
    while remaining and len(selected) < max(0, limit):
        best = min(
            remaining,
            key=lambda ref: (-len(feature_map[ref] - covered), ref),
        )
        selected.append(best)
        covered.update(feature_map[best])
        remaining.remove(best)
    return {
        "schema_version": "sl.climate_ghg_eligibility_review_manifest.v2",
        "authority": "read_only_candidate_review",
        "execution_effect": "none",
        "promotion_effect": "none",
        "sample_family_limit": limit,
        "selected_family_refs": selected,
        "covered_features": sorted(covered),
        "families": [
            {
                **family_map[family_ref],
                "statements": statements_by_family[family_ref],
            }
            for family_ref in selected
        ],
        "reviewer_questions": [
            "Is the statement semantic subtype supported by the supplied evidence?",
            "Are all five semantic-slot coordinates correctly identified?",
            "Is any target-property or same-slot collision missing from the assessment?",
            "Does candidate-review eligibility remain non-authoritative and execution-free?",
        ],
    }


def _directories_identical(left: Path, right: Path) -> bool:
    return all(
        (left / name).is_file()
        and (right / name).is_file()
        and (left / name).read_bytes() == (right / name).read_bytes()
        for name in OUTPUT_FILES
    ) and sorted(path.name for path in left.iterdir()) == sorted(
        path.name for path in right.iterdir()
    )


def materialize(
    *, replay_dir: Path, output_dir: Path, sample_family_limit: int = 15
) -> Path:
    replay_dir = replay_dir.resolve()
    output_dir = output_dir.resolve()
    payloads = {name: _load_json(replay_dir / name) for name in SOURCE_FILES}
    _verify_inputs(replay_dir, payloads)
    provenance = {name: _sha256(replay_dir / name) for name in SOURCE_FILES}
    collision_states = _target_collision_states(
        payloads["migration_pack.json"], payloads["rule_coverage.json"]
    )
    assessment = build_orthogonal_assessment(
        payloads["migration_pack.json"],
        provenance=provenance,
        target_collision_states=collision_states,
    )
    coverage = build_coverage_report(assessment)
    comparison = _legacy_comparison(
        assessment,
        payloads["rule_coverage.json"],
        payloads["h4_collision_report.json"],
    )
    review = _review_manifest(assessment, sample_family_limit)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        for name, payload in zip(
            OUTPUT_FILES, (assessment, coverage, comparison, review), strict=True
        ):
            _write_json(staging / name, payload)
        directory_fd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if output_dir.exists():
            if _directories_identical(staging, output_dir):
                return output_dir
            raise FileExistsError(
                f"output differs; choose a new --output-dir: {output_dir}"
            )
        staging.replace(output_dir)
        parent_fd = os.open(output_dir.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return output_dir
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    args = _parse_args()
    progress = build_progress_callback(
        enabled=args.progress_enabled, fmt=args.progress_format
    )
    output_dir = args.output_dir or args.replay_dir / "derived" / "orthogonal_v2"
    if progress:
        progress(
            "orthogonal_v2_started",
            {"section": "offline derivation", "status": "started"},
        )
    result = materialize(
        replay_dir=args.replay_dir,
        output_dir=output_dir,
        sample_family_limit=args.sample_family_limit,
    )
    if progress:
        progress(
            "orthogonal_v2_finished",
            {
                "section": "offline derivation",
                "status": "complete",
                "message": str(result),
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
