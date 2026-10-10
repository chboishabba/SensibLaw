#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_hf_selector import _fetch_manifest_cached  # noqa: E402
from src.ontology.wikidata_nat_zelph_binary_compat import (  # noqa: E402
    select_compatible_zelph_binary,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Select a Zelph binary that passes the canonical v2 manifest meta-only ABI probe."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest, _headers = _fetch_manifest_cached()
    receipt = select_compatible_zelph_binary(manifest, repo_root=ROOT)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "compatible": receipt["compatible"],
        "selected_binary": receipt["selected_binary"],
        "candidate_count": len(receipt["candidates"]),
        "compatibility_ref": receipt["compatibility_ref"],
    }, indent=2, sort_keys=True))
    return 0 if receipt["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
