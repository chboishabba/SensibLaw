#!/usr/bin/env python3
"""Read-only B1 authority-fixture diagnosis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.hierarchy_diagnostic import (
    diagnose_authored_hierarchy,
    search_existing_authored_hierarchies,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref")
    parser.add_argument("--search-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = {
        "selected": diagnose_authored_hierarchy(
            args.database_url,
            run_ref=args.run_ref,
            document_ref=args.document_ref,
        ),
        "existing_valid_fixtures": (
            list(search_existing_authored_hierarchies(args.database_url, limit=args.limit))
            if args.search_existing
            else []
        ),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
