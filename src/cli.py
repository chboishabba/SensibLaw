import argparse
import json
from datetime import datetime, date
from pathlib import Path

from .storage import VersionedStore


# graph query utilities
from .graph.query import (
    load_graph,
    search_by_citation,
    search_by_tag,
    search_by_type,
    traverse_edges,
)


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

    graph_parser = sub.add_parser("graph", help="Graph utilities")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")

    graph_query = graph_sub.add_parser("query", help="Query a graph JSON file")
    graph_query.add_argument(
        "--graph", dest="graph_path", required=True, help="Path to graph JSON"
    )
    group = graph_query.add_mutually_exclusive_group()
    group.add_argument("--type", dest="node_type", help="Filter nodes by type")
    group.add_argument("--citation", help="Filter nodes by citation")
    group.add_argument("--tag", help="Filter nodes by tag")
    graph_query.add_argument("--start", help="Start node for traversal")
    graph_query.add_argument(
        "--depth", type=int, default=1, help="Traversal depth from start node"
    )
    graph_query.add_argument(
        "--since", help="Only include edges on or after this date (YYYY-MM-DD)"
    )
    graph_query.add_argument(
        "--min-weight", type=float, help="Only include edges with weight >= value"
    )

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
    elif args.command == "graph" and args.graph_command == "query":
        graph_data = load_graph(args.graph_path)
        if args.start:
            since = (
                datetime.fromisoformat(args.since).date() if args.since else None
            )
            result = traverse_edges(
                graph_data,
                args.start,
                depth=args.depth,
                since=since,
                min_weight=args.min_weight,
            )
        else:
            if args.node_type:
                nodes = search_by_type(graph_data, args.node_type)
            elif args.citation:
                nodes = search_by_citation(graph_data, args.citation)
            elif args.tag:
                nodes = search_by_tag(graph_data, args.tag)
            else:
                nodes = []
            result = {"nodes": nodes, "edges": []}
        print(json.dumps(result))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
