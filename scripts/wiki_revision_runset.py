#!/usr/bin/env python3
"""Small helper to run the common Wikipedia revision-monitor command sets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = ROOT / "SensibLaw"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
PACK_RUNNER = ROOT / "SensibLaw" / "scripts" / "wiki_revision_pack_runner.py"
SELF = ROOT / "SensibLaw" / "scripts" / "wiki_revision_runset.py"
MONITOR_PACK = ROOT / "SensibLaw" / "data" / "source_packs" / "wiki_revision_monitor_v1.json"
CONTESTED_PACK = ROOT / "SensibLaw" / "data" / "source_packs" / "wiki_revision_contested_v1.json"


def _python() -> str:
    return str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)


def _run(cmd: list[str], *, cwd: Path) -> int:
    print("$", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(cwd))
    return int(completed.returncode)


def _write_smoke_pack(path: Path, *, title: str, pack_id: str) -> None:
    payload = {
        "pack_id": pack_id,
        "version": 1,
        "scope": "single-article smoke pack",
        "provenance": {"created_on": "2026-03-09", "purpose": "smoke test"},
        "history_defaults": {
            "max_revisions": 5,
            "window_days": 14,
            "max_candidate_pairs": 1,
            "section_focus_limit": 3,
        },
        "articles": [
            {
                "article_id": f"smoke_{title.lower().replace(' ', '_').replace('.', '')}",
                "wiki": "enwiki",
                "title": title,
                "role": "stress",
                "topics": ["smoke"],
                "review_context": {
                    "diagnostic_topics": ["smoke"],
                    "notes": ["single article smoke test"],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run useful Wikipedia revision-monitor command sets.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tests", help="Run the focused pytest slice for the revision monitor.")

    smoke = sub.add_parser("smoke", help="Run a one-article live smoke pack.")
    smoke.add_argument("--title", default="Donald Trump", help="Smoke-test article title")
    smoke.add_argument("--pack-path", type=Path, default=Path("/tmp/wiki_revision_smoke_one.json"))
    smoke.add_argument("--state-db", type=Path, default=Path("/tmp/wiki_revision_smoke_one.sqlite"))
    smoke.add_argument("--out-dir", type=Path, default=Path("/tmp/wiki_revision_smoke_one_out"))
    smoke.add_argument("--summary-format", choices=("human", "json"), default="human")

    monitor = sub.add_parser("monitor", help="Run the ontology-stress monitor pack.")
    monitor.add_argument("--summary-format", choices=("human", "json"), default="human")

    contested = sub.add_parser("contested", help="Run the contested live pack.")
    contested.add_argument("--summary-format", choices=("human", "json"), default="human")

    all_cmd = sub.add_parser("all", help="Run tests, smoke, monitor, then contested.")
    all_cmd.add_argument("--summary-format", choices=("human", "json"), default="human")

    args = parser.parse_args(argv)
    py = _python()

    if args.cmd == "tests":
        return _run(
            [
                py,
                "-m",
                "pytest",
                "-q",
                "tests/test_wiki_revision_pack_runner.py",
                "tests/test_wiki_revision_harness.py",
                "tests/text/test_similarity.py",
            ],
            cwd=SENSIBLAW_ROOT,
        )

    if args.cmd == "smoke":
        pack_path = Path(args.pack_path)
        _write_smoke_pack(pack_path, title=str(args.title), pack_id="wiki_revision_smoke_one")
        return _run(
            [
                py,
                str(PACK_RUNNER),
                "--pack",
                str(pack_path),
                "--state-db",
                str(args.state_db),
                "--out-dir",
                str(args.out_dir),
                "--summary-format",
                str(args.summary_format),
            ],
            cwd=ROOT,
        )

    if args.cmd == "monitor":
        return _run([py, str(PACK_RUNNER), "--pack", str(MONITOR_PACK), "--summary-format", str(args.summary_format)], cwd=ROOT)

    if args.cmd == "contested":
        return _run([py, str(PACK_RUNNER), "--pack", str(CONTESTED_PACK), "--summary-format", str(args.summary_format)], cwd=ROOT)

    if args.cmd == "all":
        for cmd in (
            [py, str(SELF), "tests"],
            [py, str(SELF), "smoke", "--summary-format", str(args.summary_format)],
            [py, str(SELF), "monitor", "--summary-format", str(args.summary_format)],
            [py, str(SELF), "contested", "--summary-format", str(args.summary_format)],
        ):
            rc = _run(cmd, cwd=ROOT)
            if rc != 0:
                return rc
        return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
