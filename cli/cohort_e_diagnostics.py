from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ontology.wikidata_cohort_e_diagnostics import (
    build_cohort_e_diagnostic_report,
    summarize_cohort_e_reports,
)
from src.ontology.wikidata_cohort_e_summary_index import build_summary_index

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wikidata"


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Cohort E diagnostics report.")
    parser.add_argument(
        "--samples",
        type=Path,
        default=_FIXTURE_DIR / "wikidata_nat_cohort_e_split_axis_sample_20260403.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_FIXTURE_DIR / "wikidata_nat_cohort_e_diagnostic_report_20260403.json",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=_FIXTURE_DIR / "wikidata_nat_cohort_e_diagnostic_summary_20260403.json",
    )
    parser.add_argument(
        "--summaries",
        type=Path,
        nargs="+",
        help="Paths to existing summary JSON files for aggregation.",
    )
    parser.add_argument(
        "--index-output",
        type=Path,
        help="Write the aggregated disagreement index built from summaries.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Emit one diagnostic report per successive sample pair.",
    )
    args = parser.parse_args()

    samples = json.loads(args.samples.read_text(encoding="utf-8"))
    reports: list[dict[str, object]] = []
    sample_list = samples.get("samples")
    if args.batch:
        if isinstance(sample_list, list):
            total = len(sample_list)
            for index in range(total - 1):
                primary = sample_list[index]
                for reference_index in range(index + 1, total):
                    reference = sample_list[reference_index]
                    report = build_cohort_e_diagnostic_report(
                        primary_candidate=primary,
                        reference_candidates=[reference],
                        max_comparisons=1,
                    )
                    reports.append(report)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
            summary = summarize_cohort_e_reports(reports)
        else:
            summary = samples
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        primary = samples["samples"][0]
        references = samples["samples"][1:]
        report = build_cohort_e_diagnostic_report(
            primary_candidate=primary,
            reference_candidates=references,
            max_comparisons=min(2, len(references)),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = summarize_cohort_e_reports([report])
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.summaries and args.index_output:
        _write_summary_index(args.summaries, args.index_output)


def _write_summary_index(summary_paths: Iterable[Path], output: Path) -> None:
    summaries = []
    for summary_path in summary_paths:
        summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))
    index = build_summary_index(summaries)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
