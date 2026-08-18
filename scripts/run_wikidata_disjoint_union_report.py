from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ontology.wikidata_disjoint_union import project_wikidata_disjoint_union_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the full finite-KB P2738 disjoint-union contract"
    )
    parser.add_argument("--input", type=Path, required=True, help="Pinned Wikidata slice JSON")
    parser.add_argument("--output", type=Path, help="Optional report JSON path")
    args = parser.parse_args(argv)

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = project_wikidata_disjoint_union_payload(payload)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
