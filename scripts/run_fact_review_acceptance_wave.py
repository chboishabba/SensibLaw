#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import (  # noqa: E402
    build_fact_review_acceptance_batch_report,
    build_fact_review_acceptance_fixture_set,
    build_fact_review_acceptance_report,
    build_fact_review_workbench_payload,
    default_fact_review_fixture_manifest_path,
)


def _print_human(report: dict) -> None:
    print(f"Wave: {report['wave']}")
    print(f"Fixtures: {report['fixture_count']}")
    for fixture in report.get("fixtures", []):
        summary = fixture.get("summary") or {}
        print(
            f"- {fixture.get('fixture_id')} [{fixture.get('fixture_kind')}/{fixture.get('workflow_kind')}] "
            f"pass={summary.get('pass_count', 0)} partial={summary.get('partial_count', 0)} fail={summary.get('fail_count', 0)}"
        )
        for story in fixture.get("stories", []):
            if story.get("status") == "pass":
                continue
            failed = ",".join(story.get("failed_check_ids") or [])
            print(f"    {story.get('story_id')}: {story.get('status')} ({failed})")
    if report.get("gaps"):
        print("Top gaps:")
        for gap in report["gaps"][:5]:
            print(f"  - {gap['gap_tag']}: {gap['count']} ({', '.join(gap['stories'])})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build canonical Mary-parity acceptance fixtures and run a batch acceptance wave.")
    parser.add_argument("--db-path", type=Path, default=Path(".cache_local/itir.sqlite"))
    parser.add_argument("--manifest-path", type=Path, default=None)
    parser.add_argument(
        "--wave",
        choices=[
            "wave1_legal",
            "wave2_balanced",
            "wave3_trauma_advocacy",
            "wave3_public_knowledge",
            "wave4_family_law",
            "wave4_medical_regulatory",
            "wave5_handoff_false_coherence",
        ],
        default="wave1_legal",
    )
    parser.add_argument("--fixture-id", action="append", dest="fixture_ids", default=[])
    parser.add_argument("--workflow-kind", default=None)
    parser.add_argument("--format", choices=["json", "human"], default="json")
    args = parser.parse_args(argv)

    manifest_path = args.manifest_path or default_fact_review_fixture_manifest_path(args.wave)
    built_fixtures = build_fact_review_acceptance_fixture_set(
        args.db_path,
        manifest_path=manifest_path,
        fixture_ids=args.fixture_ids or None,
        workflow_kind=args.workflow_kind,
        wave=args.wave,
    )

    fixture_reports: list[dict] = []
    with sqlite3.connect(str(args.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for fixture in built_fixtures:
            workbench = build_fact_review_workbench_payload(conn, run_id=fixture["fact_run_id"])
            acceptance = build_fact_review_acceptance_report(
                workbench,
                fixture_kind=str(fixture.get("fixture_kind") or "unknown"),
                wave=args.wave,
                story_ids=list(fixture.get("target_story_ids") or []),
            )
            fixture_reports.append({"fixture": fixture, "acceptance": acceptance})

    batch_report = build_fact_review_acceptance_batch_report(fixture_reports, wave=args.wave)
    batch_report["manifest_path"] = str(manifest_path.resolve())
    batch_report["db_path"] = str(args.db_path.resolve())

    if args.format == "human":
        _print_human(batch_report)
    else:
        print(json.dumps(batch_report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
