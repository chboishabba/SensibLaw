from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.ontology import wikidata_grounding_depth


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build grounding depth batch for Nat review packets"
    )
    parser.add_argument(
        "--summary",
        required=True,
        type=Path,
        help="path to grounding-depth summary fixture",
    )
    parser.add_argument(
        "--packets",
        required=True,
        type=Path,
        help="path to review packet list fixture",
    )
    parser.add_argument(
        "--outfile",
        type=Path,
        default=None,
        help="path to write the grounding batch output (defaults to stdout)",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="path to write the grounding evidence report JSON",
    )
    parser.add_argument(
        "--compare",
        action="append",
        type=Path,
        default=[],
        help="paths to grounding batch JSONs to include in the comparison report",
    )
    parser.add_argument(
        "--comparison-out",
        type=Path,
        default=None,
        help="path to write the grounding comparison JSON",
    )
    parser.add_argument(
        "--scorecard-run",
        action="append",
        default=[],
        help="run_id=path for grounding comparison files contributing to the scorecard",
    )
    parser.add_argument(
        "--scorecard-out",
        type=Path,
        default=None,
        help="path to write the grounding evidence scorecard JSON",
    )
    args = parser.parse_args(argv)

    summary_source = _read_json(args.summary)
    summary = wikidata_grounding_depth.build_grounding_depth_summary(fixture=summary_source)
    packets = json.loads(args.packets.read_text(encoding="utf-8"))
    batch = wikidata_grounding_depth.build_grounding_depth_batch(
        review_packets=packets,
        grounding_summary=summary,
    )
    report = wikidata_grounding_depth.build_grounding_depth_evidence_report(
        grounding_summary=summary
    )
    comparison_batches = []
    for path in args.compare:
        comparison_batches.append(json.loads(path.read_text(encoding="utf-8")))
    comparison = None
    if comparison_batches:
        comparison = wikidata_grounding_depth.build_grounding_depth_comparison(
            batches=comparison_batches
        )
    output_text = json.dumps(batch, indent=2)
    if args.outfile:
        args.outfile.write_text(output_text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(output_text + "\n")
    if args.report_out:
        args.report_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.comparison_out and comparison is not None:
        args.comparison_out.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    if args.scorecard_run and args.scorecard_out:
        runs: list[Mapping[str, Any]] = []
        for spec in args.scorecard_run:
            if "=" not in spec:
                raise ValueError("scorecard-run must be run_id=path")
            run_id, run_path_str = spec.split("=", 1)
            runs.append(
                {
                    "run_id": run_id,
                    "comparison": json.loads(Path(run_path_str).read_text(encoding="utf-8")),
                }
            )
        scorecard = wikidata_grounding_depth.build_grounding_depth_scorecard(runs=runs)
        args.scorecard_out.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    return 0
