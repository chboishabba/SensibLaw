#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_affidavit_coverage_review import write_affidavit_coverage_review


ARTIFACT_VERSION = "au_dense_affidavit_coverage_review_v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
SOURCE_SLICE_PATH = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "au_real_transcript_dense_substrate_v1" / "au_real_transcript_dense_substrate_v1.json"
AFFIDAVIT_DRAFT_PATH = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION / "au_dense_affidavit_draft_v1.txt"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION


def build_au_dense_affidavit_coverage_review(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    source_payload = json.loads(SOURCE_SLICE_PATH.read_text(encoding="utf-8"))
    affidavit_text = AFFIDAVIT_DRAFT_PATH.read_text(encoding="utf-8")
    return write_affidavit_coverage_review(
        output_dir=output_dir,
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path=str(SOURCE_SLICE_PATH.relative_to(REPO_ROOT)),
        affidavit_path=str(AFFIDAVIT_DRAFT_PATH.relative_to(REPO_ROOT)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the checked AU dense-substrate affidavit-coverage review artifact.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the AU dense affidavit-coverage review artifact will be written.",
    )
    args = parser.parse_args()
    result = build_au_dense_affidavit_coverage_review(Path(args.output_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
