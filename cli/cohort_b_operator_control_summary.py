from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.ontology.wikidata_nat_cohort_b_operator_control_summary import (
    build_nat_cohort_b_operator_control_summary,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wikidata"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize Cohort B operator control summary from evidence indexes."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        default=[
            _FIXTURE_DIR / "wikidata_nat_cohort_b_operator_evidence_index_20260402.json",
            _FIXTURE_DIR / "wikidata_nat_cohort_b_operator_evidence_index_case2_20260402.json",
        ],
        help="Cohort B evidence-index JSON files to summarize.",
    )
    parser.add_argument(
        "--min-ready-indexes",
        type=int,
        default=2,
        help="Minimum ready indexes required for review_control_ready status.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_FIXTURE_DIR / "wikidata_nat_cohort_b_operator_control_summary_20260402.json",
        help="Path to write the Cohort B control summary JSON output.",
    )
    args = parser.parse_args(argv)

    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
    summary = build_nat_cohort_b_operator_control_summary(
        payloads,
        min_ready_indexes=args.min_ready_indexes,
    )

    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
