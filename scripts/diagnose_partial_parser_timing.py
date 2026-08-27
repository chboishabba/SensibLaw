#!/usr/bin/env python3
"""Report timeout-safe pure spaCy work from durable partition receipts."""

from __future__ import annotations

import argparse
import json

from src.runtime.partial_parser_timing import load_partial_parser_timing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    args = parser.parse_args()
    result = load_partial_parser_timing(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
