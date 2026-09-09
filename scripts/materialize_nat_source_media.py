#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_media_materialization import (  # noqa: E402
    materialize_source_fetch_dispatch,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-verify persisted Nat P854 source blobs and materialize PDF/HTML "
            "through the existing canonical-text media adapters."
        )
    )
    parser.add_argument("--source-dispatch", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--materialized-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_dispatch = json.loads(args.source_dispatch.read_text(encoding="utf-8"))
    if not isinstance(source_dispatch, dict):
        raise ValueError("expected source-fetch dispatch JSON object")

    dispatch = materialize_source_fetch_dispatch(
        source_dispatch,
        artifact_store_dir=args.artifact_dir,
        materialized_store_dir=args.materialized_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dispatch, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "dispatch_ref": dispatch["dispatch_ref"],
                "source_fetch_receipt_count": dispatch["source_fetch_receipt_count"],
                "materialization_count": dispatch["materialization_count"],
                "materialized_source_count": dispatch["materialized_source_count"],
                "counts_by_materialization_state": dispatch[
                    "counts_by_materialization_state"
                ],
                "canonical_char_count": dispatch["canonical_char_count"],
                "proposition_support_evaluated": dispatch[
                    "proposition_support_evaluated"
                ],
                "authority_evaluated": dispatch["authority_evaluated"],
                "semantic_promotion_performed": dispatch[
                    "semantic_promotion_performed"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
