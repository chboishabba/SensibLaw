#!/usr/bin/env python3
"""Run the rolling Wikipedia revision monitor over a bounded article pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.wiki_timeline.revision_pack_runner import default_out_dir_for_pack, human_summary, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded rolling Wikipedia revision pack runner.")
    parser.add_argument(
        "--pack",
        type=Path,
        default=Path("SensibLaw/data/source_packs/wiki_revision_monitor_v1.json"),
        help="Article pack manifest (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for export artifacts (default: derived from --pack pack_id)",
    )
    parser.add_argument(
        "--state-db",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_revision_harness.sqlite"),
        help="Dedicated SQLite state DB (default: %(default)s)",
    )
    parser.add_argument(
        "--bridge-db",
        type=Path,
        default=Path(".cache_local/itir.sqlite"),
        help="Optional bridge DB used for bounded auto-join context (default: %(default)s)",
    )
    parser.add_argument(
        "--summary-format",
        choices=("json", "human"),
        default="json",
        help="stdout summary format (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    payload = run(
        pack_path=args.pack,
        out_dir=args.out_dir or default_out_dir_for_pack(args.pack),
        state_db_path=args.state_db,
        bridge_db_path=args.bridge_db,
    )
    if args.summary_format == "human":
        print(human_summary(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
