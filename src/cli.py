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

    extract_parser = sub.add_parser("extract", help="Extraction helpers")
    extract_parser.add_argument("--text", help="Provision text")
    extract_sub = extract_parser.add_subparsers(dest="extract_command")

    extract_text = extract_sub.add_parser("rules", help="Extract rules from text")
    extract_text.add_argument("--text", required=True, help="Provision text")

    extract_frl = extract_sub.add_parser("frl", help="Fetch Acts from the FRL API")
    extract_frl.add_argument("--data", type=Path, help="Path to JSON payload for tests")
    extract_frl.add_argument("--api-url", default="https://example.com", help="FRL API base URL")

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

    query_parser = sub.add_parser(
        "query", help="Run a concept query or case lookup over the knowledge base"
    )
    query_parser.add_argument("--text", help="Question or keyword query")
    query_parser.add_argument(
        "--graph",
        type=Path,
        help="Path to a StoryGraph JSON file representing the query",
    )
    query_sub = query_parser.add_subparsers(dest="query_command")
    case_q = query_sub.add_parser("case", help="Look up a case by identifier")
    case_q.add_argument("--id", required=True, help="Case identifier")
    case_q.add_argument("--year", type=int, default=1992, help="Year of judgment")

    graph_parser = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    subgraph_parser = graph_sub.add_parser("subgraph", help="Extract subgraph")
    subgraph_parser.add_argument("--seed", required=True, help="Seed node identifier")
    subgraph_parser.add_argument("--hops", type=int, default=1, help="Number of hops")
    subgraph_parser.add_argument("--graph-file", type=Path, help="Graph JSON file (use '-' for stdin)")

    tests_parser = sub.add_parser("tests", help="Run declarative tests")
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser("run", help="Run tests against a story")
    tests_run.add_argument("--ids", nargs="+", required=True, help="Test IDs")
    tests_run.add_argument("--story", type=Path, required=True, help="Story JSON file")

    cases_parser = sub.add_parser("cases", help="Case operations")
    cases_sub = cases_parser.add_subparsers(dest="cases_command")
    cases_treat = cases_sub.add_parser("treatment", help="Fetch case treatment")
    cases_treat.add_argument("--case-id", required=True, help="Case identifier")

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
        if args.extract_command == "rules" or (args.extract_command is None and args.text):
            from .rules.extractor import extract_rules

            rules = extract_rules(args.text)
            print(json.dumps([r.__dict__ for r in rules]))
        elif args.extract_command == "frl":
            from .ingestion.frl import fetch_acts

            payload = json.loads(args.data.read_text()) if args.data else None
            nodes, edges = fetch_acts(args.api_url, data=payload)
            print(json.dumps({"nodes": nodes, "edges": edges}))
        else:
            parser.print_help()
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
    elif args.command == "query":
        if args.query_command == "case":
            from .api import routes
            from .graph.models import EdgeType, GraphEdge, GraphNode, NodeType
            from .ingestion import hca

            nodes, edges = hca.crawl_year(args.year)
            for n in nodes:
                meta = {k: v for k, v in n.items() if k not in {"id", "type"}}
                routes._graph.add_node(
                    GraphNode(type=NodeType.DOCUMENT, identifier=n["id"], metadata=meta)
                )
            for e in edges:
                routes._graph.add_edge(
                    GraphEdge(type=EdgeType.CITES, source=e["from"], target=e["to"])
                )
            case = next((n for n in nodes if n["id"] == args.id), None)
            if case is None:
                print("{}")
            else:
                cites = [e["to"] for e in edges if e["from"] == args.id]
                result = {
                    "catchwords": case.get("catchwords", []),
                    "citations": cites,
                }
                print(json.dumps(result))
        else:
            from .pipeline import build_cloud, match_concepts, normalise
            from .pipeline.input_handler import parse_input

            if args.graph:
                data = json.loads(args.graph.read_text())
                raw_query = parse_input(data)
            else:
                raw_query = parse_input(args.text)

            text = normalise(raw_query)
            concepts = match_concepts(text)
            cloud = build_cloud(concepts)
            print(json.dumps({"cloud": cloud}))
    elif args.command == "graph":
        if args.graph_command == "subgraph":
            if args.graph_file:
                import sys
                from .graph.proof_tree import Graph, Node, Edge, build_subgraph, to_dot

                if str(args.graph_file) == "-":
                    data = json.load(sys.stdin)
                else:
                    data = json.loads(args.graph_file.read_text())

                g = Graph()
                for n in data.get("nodes", []):
                    g.add_node(Node(n["id"], n["type"], {"label": n.get("title", n["id"])}))
                for e in data.get("edges", []):
                    g.add_edge(Edge(e["from"], e["to"], e["type"], {"label": e.get("type")}))
                nodes, edges = build_subgraph(g, {args.seed}, hops=args.hops)
                print(to_dot(nodes, edges))
            else:
                from .api.routes import generate_subgraph

                result = generate_subgraph(args.seed, args.hops)
                print(json.dumps(result))
        else:
            parser.print_help()
    elif args.command == "tests":
        if args.tests_command == "run":
            from .api.routes import execute_tests

            story = json.loads(args.story.read_text())
            result = execute_tests(args.ids, story)
            print(json.dumps(result))
        else:
            parser.print_help()
    elif args.command == "cases":
        if args.cases_command == "treatment":
            from .api.routes import fetch_case_treatment

            result = fetch_case_treatment(args.case_id)
            print(json.dumps(result))
        else:
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
