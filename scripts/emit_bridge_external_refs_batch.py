#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = Path(__file__).resolve().parents[1]
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Emit ontology external-ref batches from deterministic bridge hits.")
    ap.add_argument("--text", help="Inline text to tokenize")
    ap.add_argument("--text-file", type=Path, help="Path to text file")
    ap.add_argument("--anchor-map", type=Path, required=True, help="JSON map of canonical_ref -> {actor_id|concept_code}")
    ap.add_argument("--output", type=Path, help="Optional path to write batch JSON")
    args = ap.parse_args(argv)

    if not args.text and not args.text_file:
        raise SystemExit("provide --text or --text-file")
    text = args.text if args.text is not None else args.text_file.read_text(encoding="utf-8")
    anchor_map = json.loads(args.anchor_map.read_text(encoding="utf-8"))

    from src.ontology.entity_bridge import build_external_refs_batch_from_text

    payload = build_external_refs_batch_from_text(text, anchor_map)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
