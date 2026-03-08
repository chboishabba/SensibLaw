#!/usr/bin/env python3
"""Compare two Wikipedia revisions and optional AAO payloads.

This harness is read-only and review-oriented:
- compares previous vs current revision metadata
- reports source/extraction similarity
- summarizes local graph-facing impact
- surfaces claim-bearing / attribution deltas
- emits issue packets plus a compact triage dashboard
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.wiki_timeline.revision_harness import build_revision_comparison_report


def _load_json(path: Optional[Path]) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compare two Wikipedia revision artifacts.")
    ap.add_argument("--previous-snapshot", type=Path, help="Previous wiki_pull_api snapshot JSON.")
    ap.add_argument("--current-snapshot", type=Path, help="Current wiki_pull_api snapshot JSON.")
    ap.add_argument("--previous-aoo", type=Path, help="Previous wiki_timeline_aoo_extract JSON.")
    ap.add_argument("--current-aoo", type=Path, help="Current wiki_timeline_aoo_extract JSON.")
    ap.add_argument("--review-context", type=Path, help="Optional review-context JSON keyed by event_id.")
    ap.add_argument("--output", type=Path, help="Optional output path for the report.")
    args = ap.parse_args(argv)

    report = build_revision_comparison_report(
        previous_snapshot=_load_json(args.previous_snapshot),
        current_snapshot=_load_json(args.current_snapshot),
        previous_payload=_load_json(args.previous_aoo),
        current_payload=_load_json(args.current_aoo),
        review_context=_load_json(args.review_context),
    )

    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())
