from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.ontology.wikidata_nat_cohort_b_operator_evidence_index import (
    build_nat_cohort_b_operator_evidence_index,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wikidata"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize Cohort B operator evidence index from batch reports."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        default=[
            _FIXTURE_DIR / "wikidata_nat_cohort_b_operator_batch_report_20260402.json",
            _FIXTURE_DIR / "wikidata_nat_cohort_b_operator_batch_report_case2_20260402.json",
        ],
        help="Batch-report JSON files to aggregate into the Cohort B evidence index.",
    )
    parser.add_argument(
        "--min-ready-batches",
        type=int,
        default=2,
        help="Minimum ready batches required before index status can be review_index_ready.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_FIXTURE_DIR / "wikidata_nat_cohort_b_operator_evidence_index_20260402.json",
        help="Path to write the materialized Cohort B evidence index.",
    )
    args = parser.parse_args(argv)

    batch_reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in args.inputs
    ]
    payload = build_nat_cohort_b_operator_evidence_index(
        batch_reports,
        min_ready_batches=args.min_ready_batches,
    )
    output_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
