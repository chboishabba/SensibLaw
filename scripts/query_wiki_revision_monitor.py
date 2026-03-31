#!/usr/bin/env python3
"""Query bounded wiki revision monitor runs and contested-region graph artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.wiki_timeline.revision_monitor_query import build_query_payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Query wiki revision monitor runs and contested-region graph artifacts.")
    ap.add_argument("--db-path", required=True)
    ap.add_argument("--pack-id", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--article-id", default=None)
    args = ap.parse_args(argv)

    payload = build_query_payload(
        db_path=Path(args.db_path),
        pack_id=args.pack_id,
        run_id=args.run_id,
        article_id=args.article_id,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
