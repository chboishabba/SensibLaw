#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"

ARTIFACT_VERSION = "review_geometry_normalized_summary_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
SOURCE_ARTIFACTS = [
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "au_affidavit_coverage_review_v1" / "affidavit_coverage_review_v1.json",
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "au_dense_affidavit_coverage_review_v1" / "affidavit_coverage_review_v1.json",
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "wikidata_structural_review_v1" / "wikidata_structural_review_v1.json",
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "wikidata_dense_structural_review_v1" / "wikidata_dense_structural_review_v1.json",
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "gwb_public_review_v1" / "gwb_public_review_v1.json",
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "gwb_broader_review_v1" / "gwb_broader_review_v1.json",
]


def _load_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("normalized_metrics_v1")
    if not isinstance(metrics, dict):
        raise ValueError(f"Artifact missing normalized_metrics_v1: {path}")
    return metrics


def build_normalized_summary(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    metrics_rows = [_load_metrics(path) for path in SOURCE_ARTIFACTS]
    payload = {
        "version": ARTIFACT_VERSION,
        "artifacts": metrics_rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


def build_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Review Geometry Normalized Summary",
        "",
        "| Artifact | Items A/R/H | Sources A/R/H | RR ratio | Dominant workload | Signal density | Row density | Bundle density |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in payload.get("artifacts", []):
        item_status = row["review_item_status_counts"]
        source_status = row["source_status_counts"]
        lines.append(
            "| "
            f"{row['artifact_id']} | "
            f"{item_status['accepted']}/{item_status['review_required']}/{item_status['held']} | "
            f"{source_status['accepted']}/{source_status['review_required']}/{source_status['held']} | "
            f"{row['review_required_source_ratio']:.6f} | "
            f"{row['dominant_primary_workload']} | "
            f"{row['candidate_signal_density']:.6f} | "
            f"{row['provisional_row_density']:.6f} | "
            f"{row['provisional_bundle_density']:.6f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the normalized cross-lane review-geometry summary.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the normalized summary artifact will be written.",
    )
    args = parser.parse_args()
    print(json.dumps(build_normalized_summary(Path(args.output_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
