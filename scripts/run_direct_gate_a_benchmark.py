#!/usr/bin/env python3
"""Run the canonical packed-fibre Gate-A benchmark against a migrated database."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from uuid import uuid4

from src.storage.postgres.direct_gate_a_benchmark import run_direct_gate_a_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--parser-contract-ref", required=True)
    parser.add_argument("--document-ref", default="gate-a-direct-benchmark")
    parser.add_argument("--run-ref")
    parser.add_argument("--artifact-root", type=Path, default=Path(".artifacts/gate-a"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    text = args.text_file.read_text(encoding="utf-8")
    run_ref = args.run_ref or f"gate-a-direct:{uuid4().hex}"
    receipt = run_direct_gate_a_benchmark(
        database_url=args.database_url,
        run_ref=run_ref,
        document_ref=args.document_ref,
        canonical_text=text,
        parser_contract_ref=args.parser_contract_ref,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(asdict(receipt), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
