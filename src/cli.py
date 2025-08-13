import argparse
import json
from datetime import datetime, date
from pathlib import Path

from .storage import VersionedStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="sensiblaw")
    sub = parser.add_subparsers(dest="command")

    get_parser = sub.add_parser("get", help="Retrieve a document by ID")
    get_parser.add_argument("--db", default="data/store.db", help="Path to database")
    get_parser.add_argument("--id", type=int, required=True, help="Document ID")
    get_parser.add_argument(
        "--as-at", help="Return version as of this date (YYYY-MM-DD)")

    extract_parser = sub.add_parser("extract", help="Extract rules from text")
    extract_parser.add_argument("--text", required=True, help="Provision text")

    check_parser = sub.add_parser("check", help="Check rules for issues")
    check_parser.add_argument("--rules", required=True, help="JSON encoded rules")

    fetch_parser = sub.add_parser(
        "pdf-fetch", help="Ingest a PDF and extract rules"
    )
    fetch_parser.add_argument("path", type=Path, help="Path to PDF file")
    fetch_parser.add_argument("--output", type=Path, help="Output JSON path")
    fetch_parser.add_argument("--jurisdiction", help="Jurisdiction metadata")
    fetch_parser.add_argument("--citation", help="Citation metadata")
    fetch_parser.add_argument(
        "--cultural-flags", nargs="*", help="List of cultural sensitivity flags"
    )

    dist_parser = sub.add_parser(
        "distinguish", help="Compare two cases and show reasoning"
    )
    dist_parser.add_argument(
        "--base", type=Path, required=True, help="Base case paragraphs as JSON"
    )
    dist_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate case paragraphs as JSON",
    )

    # Graph and provisioning commands
    graph_parser = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    sg_parser = graph_sub.add_parser("subgraph", help="Retrieve subgraph")
    sg_parser.add_argument("--node", action="append", help="Node identifier", default=[])
    sg_parser.add_argument("--limit", type=int, default=50)
    sg_parser.add_argument("--offset", type=int, default=0)
    sg_parser.add_argument("--dot", action="store_true", help="Output DOT format")

    treatment_parser = sub.add_parser("treatment", help="Show treatments for a document")
    treatment_parser.add_argument("--doc", required=True, help="Document identifier")
    treatment_parser.add_argument("--limit", type=int, default=50)
    treatment_parser.add_argument("--offset", type=int, default=0)
    treatment_parser.add_argument("--dot", action="store_true", help="Output DOT format")

    provision_parser = sub.add_parser("provision", help="Retrieve a provision")
    provision_parser.add_argument("--doc", required=True, help="Document identifier")
    provision_parser.add_argument("--id", required=True, help="Provision identifier")

    args = parser.parse_args()
    if args.command == "get":
        store = VersionedStore(args.db)
        if args.as_at:
            as_at = datetime.fromisoformat(args.as_at).date()
        else:
            as_at = date.today()
        doc = store.snapshot(args.id, as_at)
        if doc is None:
            print("Not found")
        else:
            print(doc.to_json())
        store.close()
    elif args.command == "extract":
        from .rules.extractor import extract_rules

        rules = extract_rules(args.text)
        print(json.dumps([r.__dict__ for r in rules]))
    elif args.command == "check":
        from .rules import Rule
        from .rules.reasoner import check_rules

        data = json.loads(args.rules)
        rules = [Rule(**r) for r in data]
        issues = check_rules(rules)
        print(json.dumps(issues))
    elif args.command == "pdf-fetch":
        from .pdf_ingest import process_pdf

        doc = process_pdf(
            args.path,
            output=args.output,
            jurisdiction=args.jurisdiction,
            citation=args.citation,
            cultural_flags=args.cultural_flags,
        )
        print(doc.to_json())
    elif args.command == "distinguish":
        from .distinguish.engine import (
            compare_cases,
            extract_case_silhouette,
        )

        base_paras = json.loads(args.base.read_text())
        cand_paras = json.loads(args.candidate.read_text())
        base = extract_case_silhouette(base_paras)
        cand = extract_case_silhouette(cand_paras)
        result = compare_cases(base, cand)
        print(json.dumps(result))
    elif args.command == "graph" and args.graph_command == "subgraph":
        from .sample_data import build_subgraph, subgraph_to_dot

        if args.limit < 1 or args.offset < 0:
            raise ValueError("limit must be positive and offset non-negative")
        data = build_subgraph(args.node, args.limit, args.offset)
        if args.dot:
            print(subgraph_to_dot(data))
        else:
            print(json.dumps(data))
    elif args.command == "treatment":
        from .sample_data import build_subgraph, subgraph_to_dot, treatments_for

        if args.limit < 1 or args.offset < 0:
            raise ValueError("limit must be positive and offset non-negative")
        edges = treatments_for(args.doc, args.limit, args.offset)
        if args.dot:
            node_ids = {e["source"] for e in edges} | {e["target"] for e in edges}
            graph = build_subgraph(list(node_ids), args.limit, args.offset)
            graph["edges"] = edges
            print(subgraph_to_dot(graph))
        else:
            print(json.dumps(edges))
    elif args.command == "provision":
        from .sample_data import get_provision

        prov = get_provision(args.doc, args.id)
        if prov is None:
            print("Not found")
        else:
            print(json.dumps(prov))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
