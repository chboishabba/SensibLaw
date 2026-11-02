#!/usr/bin/env python3
"""Export the bounded Wong 2022 candidate world as deterministic review JSON.

Usage:
  python scripts/export_wong2022_source_review.py > wong2022-review.json

This export is NOT an S29 admission, external ontology edit, or wet-lab model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.wong2022_source_review_adapter import (  # noqa: E402
    build_wong_2022_candidate_world,
)


def main() -> int:
    world = build_wong_2022_candidate_world()
    json.dump(world, sys.stdout, sort_keys=True, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
