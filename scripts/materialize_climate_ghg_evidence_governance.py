#!/usr/bin/env python3
"""Materialize derived climate-GHG evidence/governance reports offline."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.climate_ghg_evidence_governance import (  # noqa: E402
    build_evidence_outputs,
)


OUTPUT_FILES = (
    "review_adjudications.json",
    "hold_reason_inventory.json",
    "coverage_reason_inventory.json",
    "a4_attrition_explanation.json",
    "contract_proposal.json",
    "evidence_governance_manifest.json",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize offline climate-GHG evidence/governance reports."
    )
    parser.add_argument("--assessment-dir", required=True, type=Path)
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--adjudications", type=Path)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _identical(left: Path, right: Path) -> bool:
    return sorted(path.name for path in left.iterdir()) == sorted(
        path.name for path in right.iterdir()
    ) and all(
        (left / name).read_bytes() == (right / name).read_bytes()
        for name in OUTPUT_FILES
    )


def materialize(
    *,
    assessment_dir: Path,
    replay_dir: Path,
    output_dir: Path | None = None,
    adjudications_path: Path | None = None,
) -> Path:
    assessment_dir = assessment_dir.resolve()
    replay_dir = replay_dir.resolve()
    output_dir = (output_dir or assessment_dir / "evidence_governance").resolve()
    assessment = _load(assessment_dir / "orthogonal_assessment.json")
    manifest = _load(assessment_dir / "eligibility_review_manifest.json")
    migration_pack = _load(replay_dir / "migration_pack.json")
    rule_coverage = _load(replay_dir / "rule_coverage.json")
    adjudications = _load(adjudications_path.resolve()) if adjudications_path else None
    outputs = build_evidence_outputs(
        assessment=assessment,
        manifest=manifest,
        migration_pack=migration_pack,
        rule_coverage=rule_coverage,
        adjudications=adjudications,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        for name in OUTPUT_FILES:
            _write(staging / name, outputs[name])
        directory_fd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if output_dir.exists():
            if _identical(staging, output_dir):
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
    result = materialize(
        assessment_dir=args.assessment_dir,
        replay_dir=args.replay_dir,
        output_dir=args.output_dir,
        adjudications_path=args.adjudications,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
