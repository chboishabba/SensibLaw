#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fixture_path(name: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "SensibLaw" / "demo" / "narrative" / f"{name}.json"


def _parse_db_paths(raw: str, repo_root: Path) -> list[Path]:
    values = [chunk.strip() for chunk in (raw or "").split(",") if chunk.strip()]
    out: list[Path] = []
    for value in values:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (repo_root / path).resolve()
        out.append(path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bounded narrative validation/comparison artifacts.")
    parser.add_argument("--fixture", default="friendlyjordies_demo")
    parser.add_argument(
        "--archive-backed",
        action="store_true",
        help="Attempt to rebuild supported fixtures from local chat-history archives before loading static demo JSON.",
    )
    parser.add_argument(
        "--archive-dbs",
        default="~/chat_archive.sqlite,~/.chat_archive.sqlite,.chatgpt_history.sqlite3,chat-export-structurer/my_archive.sqlite",
        help="Comma-separated candidate archive DB paths used by --archive-backed.",
    )
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
    from src.reporting.narrative_fixture_refresh import build_archive_backed_fixture  # noqa: PLC0415

    fixture_path = _fixture_path(args.fixture)
    if args.archive_backed:
        generated = build_archive_backed_fixture(
            fixture_name=args.fixture,
            repo_root=repo_root,
            db_paths=_parse_db_paths(args.archive_dbs, repo_root),
        )
        if generated is not None:
            fixture_path = generated

    fixture_meta, sources = load_fixture_sources(fixture_path)
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
