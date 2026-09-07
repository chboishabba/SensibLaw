#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ontology.wikidata_nat_hf_crash_diagnosis import diagnose_hosted_partial_chunk
from src.ontology.wikidata_nat_hf_selector import _fetch_manifest_cached


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose which hosted Zelph partial-read stage first fails."
    )
    parser.add_argument("--qid", default="Q10403939")
    parser.add_argument("--chunk", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest, _headers = _fetch_manifest_cached()
    receipt = diagnose_hosted_partial_chunk(
        manifest,
        qid=args.qid,
        chunk_index=args.chunk,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "schema_version": receipt["schema_version"],
        "chunk_index": receipt["chunk_index"],
        "first_failure_stage": receipt["first_failure_stage"],
        "diagnosis_ref": receipt["diagnosis_ref"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
