#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report deterministic top-k parser/Wikidata relation neighborhoods across corpora.")
    parser.add_argument("--chat-db")
    parser.add_argument("--messenger-db")
    parser.add_argument("--run-id")
    parser.add_argument("--context-file", action="append", default=[])
    parser.add_argument("--transcript-file", action="append", default=[])
    parser.add_argument("--shell-log", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--top-n-neighbors", type=int, default=8)
    parser.add_argument("--db-path", default=".cache_local/itir.sqlite")
    parser.add_argument("--slice-name")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.reporting.relation_neighborhood_report import build_relation_neighborhood_report  # noqa: PLC0415
    from src.reporting.structure_report import load_chat_units, load_file_units, load_messenger_units  # noqa: PLC0415

    units = []
    if args.chat_db:
        units.extend(load_chat_units(args.chat_db, args.run_id))
    if args.messenger_db:
        units.extend(load_messenger_units(args.messenger_db, args.run_id))
    for path in args.context_file:
        units.extend(load_file_units(path, "context_file"))
    for path in args.transcript_file:
        units.extend(load_file_units(path, "transcript_file"))
    for path in args.shell_log:
        units.extend(load_file_units(path, "shell_log"))
    if not units:
        raise SystemExit("no corpus inputs provided")

    report = build_relation_neighborhood_report(
        units,
        top_k=args.top_k,
        top_n_neighbors=args.top_n_neighbors,
        db_path=args.db_path,
        slice_name=args.slice_name,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"units={report['unit_count']} terms={report['term_count']} dependency_mode={report['dependency_mode']}")
    print("top_topic_interconnects:")
    for row in report["top_topic_interconnects"]:
        print(f"  - {row['term']}: {row['count']}")
    print("top_terms:")
    for row in report["top_terms"]:
        print(f"- {row['top_surface']} ({row['term']}): count={row['count']} units={row['unit_count']}")
        if row["bridge_matches"]:
            for link in row["bridge_matches"]:
                print(f"    bridge: {link['curie']} via {link['matched_alias']} -> {link['canonical_ref']}")
        for neighbor in row["top_dependency_neighbors"][:3]:
            print(f"    dep: {neighbor['relation']} {neighbor['term']} ({neighbor['count']})")
        for neighbor in row["top_cooccurring_terms"][:3]:
            print(f"    co: {neighbor['term']} ({neighbor['count']})")


if __name__ == "__main__":
    main()
