#!/usr/bin/env python3
"""Run the Agda Gate-A optimized direct semantic benchmark on one source file."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from src.storage.postgres.direct_benchmark_execution import (
    run_direct_benchmark_execution,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text_file", type=Path)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--parser-contract-ref", required=True)
    parser.add_argument("--worker-count", type=int, default=2)
    parser.add_argument("--artifact-root", type=Path, default=Path(".artifacts/direct-gate-a"))
    parser.add_argument("--run-ref")
    parser.add_argument("--document-ref")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    text = args.text_file.read_text(encoding="utf-8")
    suffix = uuid4().hex
    run_ref = args.run_ref or f"direct-gate-a:{suffix}"
    document_ref = args.document_ref or f"direct-gate-a-doc:{suffix}"
    carrier = run_direct_benchmark_execution(
        database_url=args.database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        canonical_text=text,
        parser_contract_ref=args.parser_contract_ref,
        artifact_root=args.artifact_root,
        worker_count=args.worker_count,
    )
    receipt = dict(carrier["parser_receipt"])
    output = {
        "run_ref": run_ref,
        "document_ref": document_ref,
        "sentence_count": carrier.sentence_count,
        "token_count": carrier.token_count,
        "receipt": receipt,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    if not receipt.get("gate_a_benchmark_ready"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
