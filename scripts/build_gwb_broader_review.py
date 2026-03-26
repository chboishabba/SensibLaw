#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.review_geometry_profiles import get_normalized_profile
    from scripts.review_geometry_normalization import (
        compute_normalized_metrics_from_profile,
        render_normalized_metrics_markdown,
    )
except ModuleNotFoundError:
    from review_geometry_profiles import get_normalized_profile
    from review_geometry_normalization import (
        compute_normalized_metrics_from_profile,
        render_normalized_metrics_markdown,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"

ARTIFACT_VERSION = "gwb_broader_review_v1"
SOURCE_SLICE_PATH = (
    SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "zelph"
    / "gwb_broader_corpus_checkpoint_v1"
    / "gwb_broader_corpus_checkpoint_v1.json"
)
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _build_review_item_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in slice_payload.get("merged_seed_lanes", []):
        seed_id = str(lane.get("seed_id") or "").strip()
        if not seed_id:
            continue
        matched_families = list(lane.get("matched_source_families", []))
        source_families = list(lane.get("source_families", []))
        if len(matched_families) == len(source_families):
            coverage_status = "covered"
        elif matched_families:
            coverage_status = "partial"
        else:
            coverage_status = "unsupported"
        rows.append(
            {
                "review_item_id": f"seed:{seed_id}",
                "seed_id": seed_id,
                "action_summary": lane.get("action_summary"),
                "linkage_kind": lane.get("linkage_kind"),
                "coverage_status": coverage_status,
                "source_family_count": len(source_families),
                "matched_source_family_count": len(matched_families),
                "support_kinds": list(lane.get("support_kinds", [])),
                "review_statuses": list(lane.get("review_statuses", [])),
            }
        )
    return rows


def _family_row(
    *, seed_id: str, family: str, matched: bool, review_statuses: list[str], support_kinds: list[str]
) -> dict[str, Any]:
    review_status = "covered" if matched else "missing_review"
    workload_class = "support_breadth_gap" if matched else "linkage_gap"
    return {
        "source_row_id": f"{seed_id}:{family}",
        "seed_id": seed_id,
        "source_kind": "seed_family_support",
        "source_family": family,
        "review_status": review_status,
        "workload_classes": [workload_class],
        "primary_workload_class": workload_class,
        "text": f"{seed_id} in {family}",
        "candidate_anchors": [
            {"anchor_kind": "source_family", "anchor_label": family, "anchor_value": family},
            *[
                {"anchor_kind": "support_kind", "anchor_label": kind, "anchor_value": kind}
                for kind in support_kinds
            ],
            *[
                {"anchor_kind": "review_status", "anchor_label": status, "anchor_value": status}
                for status in review_statuses
            ],
        ],
    }


def _build_source_review_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in slice_payload.get("merged_seed_lanes", []):
        seed_id = str(lane.get("seed_id") or "").strip()
        matched_families = set(lane.get("matched_source_families", []))
        review_statuses = list(lane.get("review_statuses", []))
        support_kinds = list(lane.get("support_kinds", []))
        for family in lane.get("source_families", []):
            rows.append(
                _family_row(
                    seed_id=seed_id,
                    family=family,
                    matched=family in matched_families,
                    review_statuses=review_statuses,
                    support_kinds=support_kinds,
                )
            )

    for index, relation in enumerate(slice_payload.get("merged_promoted_relations", []), start=1):
        subject = relation.get("subject", {})
        obj = relation.get("object", {})
        predicate = relation.get("predicate_key")
        source_families = list(relation.get("source_families", []))
        rows.append(
            {
                "source_row_id": f"relation:{index}",
                "seed_id": None,
                "source_kind": "merged_promoted_relation",
                "source_family": ",".join(source_families),
                "review_status": "covered",
                "workload_classes": ["covered"],
                "primary_workload_class": "covered",
                "text": (
                    f"{subject.get('canonical_label')} {predicate} {obj.get('canonical_label')}"
                ),
                "candidate_anchors": [
                    {"anchor_kind": "predicate", "anchor_label": str(predicate), "anchor_value": predicate},
                    *[
                        {"anchor_kind": "source_family", "anchor_label": family, "anchor_value": family}
                        for family in source_families
                    ],
                ],
            }
        )

    for family in slice_payload.get("source_family_summaries", []):
        rows.append(
            {
                "source_row_id": f"family_summary:{family['source_family']}",
                "seed_id": None,
                "source_kind": "source_family_summary",
                "source_family": family["source_family"],
                "review_status": "missing_review",
                "workload_classes": ["event_extraction_gap"],
                "primary_workload_class": "event_extraction_gap",
                "text": (
                    f"{family['source_family']} ambiguous_events={family['ambiguous_event_count']} "
                    f"unresolved_surfaces={family['unresolved_surface_count']}"
                ),
                "candidate_anchors": [
                    {
                        "anchor_kind": "ambiguous_event_count",
                        "anchor_label": str(family["ambiguous_event_count"]),
                        "anchor_value": family["ambiguous_event_count"],
                    },
                    {
                        "anchor_kind": "unresolved_surface_count",
                        "anchor_label": str(family["unresolved_surface_count"]),
                        "anchor_value": family["unresolved_surface_count"],
                    },
                ],
            }
        )
    return rows


def _build_clusters(review_item_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    item_by_seed = {row["seed_id"]: row for row in review_item_rows}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        if row.get("seed_id") and row.get("review_status") == "missing_review":
            grouped[row["seed_id"]].append(row)
    clusters: list[dict[str, Any]] = []
    for seed_id, rows in sorted(grouped.items()):
        workload = Counter()
        anchor_rollup = Counter()
        for row in rows:
            for item in row.get("workload_classes", []):
                workload[item] += 1
            for anchor in row.get("candidate_anchors", []):
                anchor_rollup[str(anchor.get("anchor_kind"))] += 1
        clusters.append(
            {
                "cluster_id": f"cluster:{seed_id}",
                "seed_id": seed_id,
                "coverage_status": item_by_seed[seed_id]["coverage_status"],
                "candidate_source_count": len(rows),
                "dominant_workload_class": max(workload, key=workload.get),
                "workload_class_rollup": dict(sorted(workload.items())),
                "candidate_anchor_rollup": dict(sorted(anchor_rollup.items())),
            }
        )
    return clusters


def _build_provisional_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = {
        "source_family": 12,
        "support_kind": 8,
        "review_status": 5,
        "predicate": 9,
        "ambiguous_event_count": 16,
        "unresolved_surface_count": 16,
    }
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        if row.get("review_status") != "missing_review":
            continue
        for index, anchor in enumerate(row.get("candidate_anchors", []), start=1):
            kind = str(anchor.get("anchor_kind"))
            score = scores.get(kind, 5)
            rows.append(
                {
                    "provisional_review_id": f"{row['source_row_id']}#p{index}",
                    "source_row_id": row["source_row_id"],
                    "seed_id": row.get("seed_id"),
                    "anchor_kind": kind,
                    "anchor_label": str(anchor.get("anchor_label")),
                    "priority_score": score,
                }
            )
    rows.sort(key=lambda row: (-row["priority_score"], row["provisional_review_id"]))
    for rank, row in enumerate(rows, start=1):
        row["priority_rank"] = rank
    return rows


def _build_bundles(provisional_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in provisional_rows:
        source_row_id = row["source_row_id"]
        bundle = grouped.setdefault(
            source_row_id,
            {"source_row_id": source_row_id, "anchor_count": 0, "top_priority_score": 0},
        )
        bundle["anchor_count"] += 1
        bundle["top_priority_score"] = max(bundle["top_priority_score"], row["priority_score"])
    bundles = sorted(
        grouped.values(),
        key=lambda row: (-row["top_priority_score"], -row["anchor_count"], row["source_row_id"]),
    )
    for rank, row in enumerate(bundles, start=1):
        row["bundle_rank"] = rank
    return bundles


def build_gwb_broader_review(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    slice_payload = _load_json(SOURCE_SLICE_PATH)
    review_item_rows = _build_review_item_rows(slice_payload)
    source_review_rows = _build_source_review_rows(slice_payload)
    related_review_clusters = _build_clusters(review_item_rows, source_review_rows)
    provisional_review_rows = _build_provisional_rows(source_review_rows)
    provisional_review_bundles = _build_bundles(provisional_review_rows)

    summary = {
        "review_item_count": len(review_item_rows),
        "source_row_count": len(source_review_rows),
        "covered_count": sum(1 for row in source_review_rows if row["review_status"] == "covered"),
        "missing_review_count": sum(
            1 for row in source_review_rows if row["review_status"] == "missing_review"
        ),
        "related_review_cluster_count": len(related_review_clusters),
        "candidate_anchor_count": sum(
            len(row.get("candidate_anchors", [])) for row in source_review_rows
        ),
        "provisional_review_row_count": len(provisional_review_rows),
        "provisional_review_bundle_count": len(provisional_review_bundles),
        **slice_payload["summary"],
    }
    payload = {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "gwb_broader_review",
        "source_input": {"path": str(SOURCE_SLICE_PATH.relative_to(REPO_ROOT))},
        "summary": summary,
        "review_item_rows": review_item_rows,
        "source_review_rows": source_review_rows,
        "related_review_clusters": related_review_clusters,
        "provisional_review_rows": provisional_review_rows,
        "provisional_review_bundles": provisional_review_bundles,
    }
    payload["normalized_metrics_v1"] = compute_normalized_metrics_from_profile(
        profile=get_normalized_profile("gwb"),
        artifact_id="gwb_broader_review_v1",
        lane_family="gwb",
        lane_variant="broader",
        review_item_rows=review_item_rows,
        source_review_rows=source_review_rows,
        candidate_signal_count=sum(
            len(row.get("candidate_anchors", []))
            for row in source_review_rows
            if row.get("review_status") == "missing_review"
        ),
        provisional_queue_row_count=len(provisional_review_rows),
        provisional_bundle_count=len(provisional_review_bundles),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


def build_summary_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GWB Broader Review",
        "",
        f"- Review items: `{summary['review_item_count']}`",
        f"- Source rows: `{summary['source_row_count']}`",
        f"- Covered source rows: `{summary['covered_count']}`",
        f"- Missing-review source rows: `{summary['missing_review_count']}`",
        f"- Related review clusters: `{summary['related_review_cluster_count']}`",
        f"- Candidate anchors: `{summary['candidate_anchor_count']}`",
        f"- Provisional review rows: `{summary['provisional_review_row_count']}`",
        f"- Provisional review bundles: `{summary['provisional_review_bundle_count']}`",
    ]
    normalized_metrics = payload.get("normalized_metrics_v1", {})
    if isinstance(normalized_metrics, dict) and normalized_metrics:
        lines.extend(["", *render_normalized_metrics_markdown(normalized_metrics)])
    lines.extend(["", "## Top Provisional Review Bundles", ""])
    for bundle in payload["provisional_review_bundles"][:10]:
        lines.append(
            f"- `#{bundle['bundle_rank']}` `{bundle['source_row_id']}` anchors `{bundle['anchor_count']}` top-score `{bundle['top_priority_score']}`"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GWB broader review artifact.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the broader review artifact will be written.",
    )
    args = parser.parse_args()
    print(json.dumps(build_gwb_broader_review(Path(args.output_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
