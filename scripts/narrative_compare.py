#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fixture_path(name: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "SensibLaw" / "demo" / "narrative" / f"{name}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bounded narrative validation/comparison artifacts.")
    parser.add_argument("--fixture", default="friendlyjordies_demo")
    sub = parser.add_subparsers(dest="cmd", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--source-id", required=True)
    sub.add_parser("compare")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.reporting.narrative_compare import (  # noqa: PLC0415
        build_narrative_comparison_report,
        build_narrative_validation_report,
        load_fixture_sources,
    )

    fixture_meta, sources = load_fixture_sources(_fixture_path(args.fixture))
    sources_by_id = {source.source_id: source for source in sources}

    if args.cmd == "validate":
        source = sources_by_id.get(args.source_id)
        if source is None:
            raise SystemExit(f"Unknown source-id: {args.source_id}")
        payload = {
            "fixture": {
                "fixture_id": fixture_meta.get("fixture_id"),
                "label": fixture_meta.get("label"),
            },
            "report": build_narrative_validation_report(source),
            "available_sources": [row.source_id for row in sources],
        }
    else:
        if len(sources) < 2:
            raise SystemExit("Fixture must contain at least two sources for compare.")
        payload = {
            "fixture": {
                "fixture_id": fixture_meta.get("fixture_id"),
                "label": fixture_meta.get("label"),
            },
            "comparison": build_narrative_comparison_report(sources[0], sources[1]),
            "available_sources": [row.source_id for row in sources],
        }

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
