#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
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

try:
    from src.policy.affidavit_extraction_hints import (
        build_candidate_anchors as _build_candidate_anchors_impl,
        build_provisional_anchor_bundles as _build_provisional_anchor_bundles_impl,
        build_provisional_structured_anchors as _build_provisional_structured_anchors_impl,
    )
except ModuleNotFoundError:
    from policy.affidavit_extraction_hints import (
        build_candidate_anchors as _build_candidate_anchors_impl,
        build_provisional_anchor_bundles as _build_provisional_anchor_bundles_impl,
        build_provisional_structured_anchors as _build_provisional_structured_anchors_impl,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"


ARTIFACT_VERSION = "gwb_public_review_v1"
SOURCE_SLICE_PATH = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "gwb_public_handoff_v1" / "gwb_public_handoff_v1.slice.json"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
_GWB_ANCHOR_KIND_WEIGHT = {
    "calendar_reference": 30,
    "receipt": 20,
    "surface": 10,
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _year_mentions(text: str) -> list[str]:
    return re.findall(r"\b(1[0-9]{3}|20[0-9]{2}|202[0-9])\b", text or "")


def _build_review_item_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in slice_payload.get("selected_seed_lanes", []):
        seed_id = str(seed.get("seed_id") or "").strip()
        if not seed_id:
            continue
        candidate_events = int(seed.get("candidate_event_count") or 0)
        matched_events = int(seed.get("matched_event_count") or 0)
        if matched_events and matched_events == candidate_events:
            coverage_status = "covered"
        elif matched_events:
            coverage_status = "partial"
        else:
            coverage_status = "unsupported"
        rows.append(
            {
                "review_item_id": f"seed:{seed_id}",
                "seed_id": seed_id,
                "action_summary": seed.get("action_summary"),
                "support_kind": seed.get("support_kind"),
                "linkage_kind": seed.get("linkage_kind"),
                "coverage_status": coverage_status,
                "candidate_event_count": candidate_events,
                "matched_event_count": matched_events,
            }
        )
    return rows


def _build_source_review_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # Seed events
    for seed in slice_payload.get("selected_seed_lanes", []):
        seed_id = str(seed.get("seed_id") or "").strip()
        for event in seed.get("events", []) or []:
            event_id = str(event.get("event_id") or "").strip()
            source_row_id = f"{seed_id}:{event_id}" if event_id else f"{seed_id}:event"
            matched = bool(event.get("matched"))
            review_status = "covered" if matched else "missing_review"
            text = str(event.get("text") or "").strip()
            receipts = event.get("receipts", []) if isinstance(event.get("receipts"), list) else []
            anchor_candidates: list[dict[str, Any]] = []
            for receipt in receipts:
                if isinstance(receipt, dict) and receipt.get("value"):
                    anchor_candidates.append(
                        {
                            "anchor_kind": "receipt",
                            "anchor_label": str(receipt.get("value")),
                            "anchor_value": receipt.get("value"),
                        }
                    )
            anchor_candidates.extend(
                _build_candidate_anchors_impl({"calendar_reference_mentions": _year_mentions(text)})
            )
            workload_classes = []
            if matched:
                workload_classes.append("covered")
            else:
                if anchor_candidates:
                    workload_classes.append("linkage_gap")
                else:
                    workload_classes.append("event_extraction_gap")
            rows.append(
                {
                    "source_row_id": source_row_id,
                    "source_kind": "gwb_seed_event",
                    "seed_id": seed_id,
                    "event_id": event_id,
                    "text": text,
                    "receipts": receipts,
                    "matched": matched,
                    "review_status": review_status,
                    "workload_classes": workload_classes,
                    "primary_workload_class": workload_classes[0] if workload_classes else None,
                    "candidate_anchors": anchor_candidates,
                }
            )
    # Unresolved surfaces
    for surface in slice_payload.get("unresolved_surfaces", []) or []:
        surface_text = str(surface.get("surface_text") or "").strip()
        if not surface_text:
            continue
        rows.append(
            {
                "source_row_id": f"surface:{surface_text}",
                "source_kind": "unresolved_surface",
                "seed_id": None,
                "event_id": None,
                "text": surface_text,
                "receipts": [],
                "matched": False,
                "review_status": "missing_review",
                "workload_classes": ["surface_resolution_gap"],
                "primary_workload_class": "surface_resolution_gap",
                "candidate_anchors": [
                    {"anchor_kind": "surface", "anchor_label": surface_text, "anchor_value": surface_text}
                ],
            }
        )
    return rows


def _build_clusters(review_item_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    by_seed: dict[str, list[dict[str, Any]]] = {}
    for row in source_rows:
        seed_id = row.get("seed_id") or ""
        if not seed_id:
            continue
        if row.get("review_status") != "missing_review":
            continue
        by_seed.setdefault(seed_id, []).append(row)
    review_item_by_seed = {row["seed_id"]: row for row in review_item_rows}
    for seed_id, rows in sorted(by_seed.items()):
        review_item = review_item_by_seed.get(seed_id, {})
        workload_counts: dict[str, int] = {}
        for row in rows:
            for wc in row.get("workload_classes", []) or []:
                workload_counts[wc] = workload_counts.get(wc, 0) + 1
        clusters.append(
            {
                "cluster_id": f"cluster:{seed_id}",
                "seed_id": seed_id,
                "coverage_status": review_item.get("coverage_status"),
                "candidate_source_count": len(rows),
                "workload_class_rollup": sorted(
                    (
                        {"workload_class": k, "count": v}
                        for k, v in workload_counts.items()
                    ),
                    key=lambda entry: (-entry["count"], entry["workload_class"]),
                ),
                "reason_code_rollup": [],
                "candidate_source_rows": [
                    {
                        "source_row_id": row.get("source_row_id"),
                        "review_status": row.get("review_status"),
                        "primary_workload_class": row.get("primary_workload_class"),
                    }
                    for row in rows[:5]
                ],
            }
        )
    return clusters


def _rank_provisional_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provisional_rows = _build_provisional_structured_anchors_impl(
        source_rows,
        anchor_kind_weight=_GWB_ANCHOR_KIND_WEIGHT,
        dedupe=False,
    )
    rows: list[dict[str, Any]] = []
    for row in provisional_rows:
        copied = dict(row)
        provisional_anchor_id = str(copied.pop("provisional_anchor_id", "")).strip()
        if provisional_anchor_id:
            copied["provisional_review_id"] = provisional_anchor_id.replace("#anchor:", "#p")
        rows.append(copied)
    rows.sort(key=lambda r: (-int(r.get("priority_score") or 0), str(r.get("provisional_review_id") or "")))
    for rank, row in enumerate(rows, start=1):
        row["priority_rank"] = rank
    return rows


def _bundle_provisional_rows(provisional_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shared_rows: list[dict[str, Any]] = []
    for row in provisional_rows:
        copied = dict(row)
        provisional_review_id = str(copied.pop("provisional_review_id", "")).strip()
        if provisional_review_id:
            copied["provisional_anchor_id"] = provisional_review_id.replace("#p", "#anchor:")
        shared_rows.append(copied)
    bundles = _build_provisional_anchor_bundles_impl(shared_rows)
    normalized_bundles: list[dict[str, Any]] = []
    for bundle in bundles:
        normalized_bundle = dict(bundle)
        normalized_anchor_rows: list[dict[str, Any]] = []
        for row in bundle.get("anchor_rows", []):
            copied = dict(row)
            provisional_anchor_id = str(copied.pop("provisional_anchor_id", "")).strip()
            if provisional_anchor_id:
                copied["provisional_review_id"] = provisional_anchor_id.replace("#anchor:", "#p")
            normalized_anchor_rows.append(copied)
        normalized_bundle["anchor_rows"] = normalized_anchor_rows
        normalized_bundles.append(normalized_bundle)
    return normalized_bundles


def _build_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    return {
        "review_item_count": len(payload.get("review_item_rows", [])),
        "source_row_count": len(payload.get("source_review_rows", [])),
        "covered_count": sum(1 for row in payload.get("source_review_rows", []) if row.get("review_status") == "covered"),
        "missing_review_count": sum(1 for row in payload.get("source_review_rows", []) if row.get("review_status") == "missing_review"),
        "related_review_cluster_count": len(payload.get("related_review_clusters", [])),
        "candidate_anchor_count": sum(len(row.get("candidate_anchors", [])) for row in payload.get("source_review_rows", [])),
        "provisional_structured_anchor_count": len(payload.get("provisional_structured_anchors", [])),
        "provisional_anchor_bundle_count": len(payload.get("provisional_anchor_bundles", [])),
        "ambiguous_event_count": summary.get("ambiguous_event_count"),
        "selected_seed_lane_count": summary.get("selected_seed_lane_count"),
        "unresolved_surface_count": summary.get("unresolved_surface_count"),
    }


def build_gwb_public_review(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    slice_payload = _load_json(SOURCE_SLICE_PATH)
    review_item_rows = _build_review_item_rows(slice_payload)
    source_review_rows = _build_source_review_rows(slice_payload)
    related_review_clusters = _build_clusters(review_item_rows, source_review_rows)
    provisional_structured_anchors = _rank_provisional_rows(source_review_rows)
    provisional_anchor_bundles = _bundle_provisional_rows(provisional_structured_anchors)

    payload = {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "gwb_public_review",
        "source_input": {
            "path": str(SOURCE_SLICE_PATH.relative_to(REPO_ROOT)),
            "source_row_count": len(source_review_rows),
        },
        "summary": {},
        "review_item_rows": review_item_rows,
        "source_review_rows": source_review_rows,
        "related_review_clusters": related_review_clusters,
        "provisional_structured_anchors": provisional_structured_anchors,
        "provisional_anchor_bundles": provisional_anchor_bundles,
    }
    payload["summary"] = _build_summary(payload | {"summary": slice_payload.get("summary", {})})
    payload["normalized_metrics_v1"] = compute_normalized_metrics_from_profile(
        profile=get_normalized_profile("gwb"),
        artifact_id="gwb_checked_public_review_v1",
        lane_family="gwb",
        lane_variant="checked",
        review_item_rows=review_item_rows,
        source_review_rows=source_review_rows,
        candidate_signal_count=sum(
            len(row.get("candidate_anchors", []))
            for row in source_review_rows
            if row.get("review_status") == "missing_review"
        ),
        provisional_queue_row_count=len(provisional_structured_anchors),
        provisional_bundle_count=len(provisional_anchor_bundles),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


def build_summary_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# GWB Public Review",
        "",
        f"- Version: `{payload.get('version')}`",
        f"- Source rows: `{summary.get('source_row_count', 0)}`",
        f"- Review items: `{summary.get('review_item_count', 0)}`",
        f"- Covered source rows: `{summary.get('covered_count', 0)}`",
        f"- Missing-review source rows: `{summary.get('missing_review_count', 0)}`",
        f"- Related review clusters: `{summary.get('related_review_cluster_count', 0)}`",
        f"- Candidate anchors: `{summary.get('candidate_anchor_count', 0)}`",
        f"- Provisional structured anchors: `{summary.get('provisional_structured_anchor_count', 0)}`",
        f"- Provisional anchor bundles: `{summary.get('provisional_anchor_bundle_count', 0)}`",
    ]
    normalized_metrics = payload.get("normalized_metrics_v1", {})
    if isinstance(normalized_metrics, dict) and normalized_metrics:
        lines.extend(["", *render_normalized_metrics_markdown(normalized_metrics)])
    lines.extend(
        [
            "",
            "## Provisional Anchor Bundles",
            "",
        ]
    )
    bundles = payload.get("provisional_anchor_bundles", []) if isinstance(payload.get("provisional_anchor_bundles"), list) else []
    for bundle in bundles[:10]:
        lines.append(
            f"- `#{bundle.get('bundle_rank')}` `{bundle.get('source_row_id')}` anchors `{bundle.get('anchor_count')}` top-score `{bundle.get('top_priority_score')}`"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GWB public review artifact from the checked handoff slice.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the GWB public review artifact will be written.",
    )
    args = parser.parse_args()
    result = build_gwb_public_review(Path(args.output_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
