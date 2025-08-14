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
        "distinguish", help="Compare a story against a case silhouette"
    )
    dist_parser.add_argument(
        "--case",
        required=True,
        help="Neutral citation identifying the base case",
    )
    dist_parser.add_argument(
        "--story",
        type=Path,
        required=True,
        help="Path to a fact-tagged story JSON file",
    )

    concepts_parser = sub.add_parser("concepts", help="Concept operations")
    concepts_sub = concepts_parser.add_subparsers(dest="concepts_command")
    concepts_match = concepts_sub.add_parser(
        "match", help="Match concept triggers within text"
    )
    concepts_match.add_argument(
        "--patterns-file",
        type=Path,
        required=True,
        help="JSON file mapping phrases to concept identifiers",
    )
    concepts_match.add_argument("--text", required=True, help="Text to match")

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
    subgraph_parser.add_argument(
        "--seeds",
        nargs="+",
        required=True,
        help="Seed node identifiers",
    )
    subgraph_parser.add_argument(
        "--hops", type=int, default=1, help="Number of hops"
    )
    subgraph_parser.add_argument(
        "--as-at",
        help="Only include nodes/edges on or before this date (YYYY-MM-DD)",
    )
    subgraph_parser.add_argument(
        "--graph-file",
        type=Path,
        help="Graph JSON file (use '-' for stdin)",
    )
    subgraph_parser.add_argument(
        "--dot",
        action="store_true",
        help="Output Graphviz DOT instead of JSON",
    )

    tests_parser = sub.add_parser("tests", help="Run declarative tests")
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser("run", help="Run checklist tests against a story")
    tests_run.add_argument(
        "--tests-file", type=Path, required=True, help="Checklist JSON file"
    )
    tests_run.add_argument(
        "--story-file", type=Path, required=True, help="Story JSON file"
    )

    cases_parser = sub.add_parser("cases", help="Case operations")
    cases_sub = cases_parser.add_subparsers(dest="cases_command")
    cases_treat = cases_sub.add_parser("treatment", help="Fetch case treatment")
    cases_treat.add_argument("--case-id", required=True, help="Case identifier")

    tools_parser = sub.add_parser("tools", help="Utility tools")
    tools_sub = tools_parser.add_subparsers(dest="tools_command")
    claim_builder = tools_sub.add_parser(
        "claim-builder", help="Interactively build a claim"
    )
    claim_builder.add_argument(
        "--dir",
        type=Path,
        default=Path("data/claims"),
        help="Directory to save claim files",
    )

    intake_parser = sub.add_parser("intake", help="Email intake operations")
    intake_sub = intake_parser.add_subparsers(dest="intake_command")
    intake_parse = intake_sub.add_parser(
        "parse", help="Parse an email mailbox into claim stubs"
    )
    intake_parse.add_argument(
        "--mailbox",
        required=True,
        help="IMAP URL or directory containing .eml files",
    )
    intake_parse.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory for generated claim stubs",
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
        from .distinguish.loader import load_case_silhouette
        from .distinguish.engine import compare_story_to_case

        case_sil = load_case_silhouette(args.case)
        story_data = json.loads(args.story.read_text())
        story_tags = story_data.get("facts", {})
        result = compare_story_to_case(story_tags, case_sil)
        print(json.dumps(result))
    elif args.command == "concepts":
        if args.concepts_command == "match":
            from .concepts.matcher import ConceptMatcher, load_patterns

            patterns = load_patterns(args.patterns_file)
            matcher = ConceptMatcher(patterns)
            hits = matcher.match(args.text)
            nodes = [
                {"id": cid, "start": span[0], "end": span[1]} for cid, span in hits
            ]
            print(json.dumps(nodes))
        else:
            parser.print_help()
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
            from .graph.proof_tree import Graph, Node, Edge, build_subgraph, to_dot

            as_at = datetime.fromisoformat(args.as_at) if args.as_at else None

            if args.graph_file:
                import sys

                if str(args.graph_file) == "-":
                    data = json.load(sys.stdin)
                else:
                    data = json.loads(args.graph_file.read_text())

                g = Graph()
                for n in data.get("nodes", []):
                    n_date = None
                    if n.get("date"):
                        try:
                            n_date = datetime.fromisoformat(n["date"])
                        except ValueError:
                            pass
                    g.add_node(
                        Node(
                            n["id"],
                            n.get("type", ""),
                            {"label": n.get("title", n["id"] )},
                            n_date,
                        )
                    )
                for e in data.get("edges", []):
                    metadata = {"label": e.get("type")}
                    if e.get("receipt"):
                        metadata["receipt"] = e.get("receipt")
                    e_date = None
                    if e.get("date"):
                        try:
                            e_date = datetime.fromisoformat(e["date"])
                        except ValueError:
                            pass
                    g.add_edge(
                        Edge(
                            e["from"],
                            e["to"],
                            e["type"],
                            metadata,
                            e_date,
                            e.get("weight"),
                        )
                    )
                nodes, edges = build_subgraph(
                    g, args.seeds, hops=args.hops, as_at=as_at
                )
                print(to_dot(nodes, edges))
            else:
                from .api.routes import generate_subgraph

                combined_nodes = {}
                combined_edges = {}
                for seed in args.seeds:
                    result = generate_subgraph(seed, args.hops)
                    for n in result.get("nodes", []):
                        nid = n.get("identifier") or n.get("id")
                        combined_nodes[nid] = n
                    for e in result.get("edges", []):
                        key = (e.get("source"), e.get("target"), e.get("type"))
                        combined_edges[key] = e
                merged = {
                    "nodes": list(combined_nodes.values()),
                    "edges": list(combined_edges.values()),
                }
                if args.dot:
                    g = Graph()
                    for n in merged["nodes"]:
                        nid = n.get("identifier") or n.get("id")
                        label = n.get("metadata", {}).get("label") or n.get(
                            "title", nid
                        )
                        n_date = None
                        if n.get("date"):
                            try:
                                n_date = datetime.fromisoformat(n["date"])
                            except ValueError:
                                pass
                        g.add_node(Node(nid, n.get("type", ""), {"label": label}, n_date))
                    for e in merged["edges"]:
                        src = e.get("source") or e.get("from")
                        tgt = e.get("target") or e.get("to")
                        typ = e.get("type")
                        meta = e.get("metadata", {})
                        label = meta.get("label", typ)
                        metadata = {"label": label}
                        receipt = meta.get("receipt") or e.get("receipt")
                        if receipt:
                            metadata["receipt"] = receipt
                        e_date = None
                        if e.get("date"):
                            try:
                                e_date = datetime.fromisoformat(e["date"])
                            except ValueError:
                                pass
                        g.add_edge(
                            Edge(src, tgt, typ, metadata, e_date, e.get("weight"))
                        )
                    if as_at:
                        nodes, edges = build_subgraph(
                            g, args.seeds, hops=args.hops, as_at=as_at
                        )
                        print(to_dot(nodes, edges))
                    else:
                        print(to_dot(g.nodes, g.edges))
                else:
                    print(json.dumps(merged))
        else:
            parser.print_help()
    elif args.command == "tests":
        if args.tests_command == "run":
            from .checklists.run import evaluate

            checklist = json.loads(args.tests_file.read_text())
            story = json.loads(args.story_file.read_text())
            tags = set(story.get("tags", []))
            result = evaluate(checklist, tags)
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
    elif args.command == "intake":
        if args.intake_command == "parse":
            from .intake.email_parser import fetch_messages, parse_email
            from .intake.stub_builder import build_stub

            messages = fetch_messages(str(args.mailbox))
            for msg in messages:
                data = parse_email(msg)
                build_stub(data, args.out)
        else:
            parser.print_help()
    elif args.command == "tools":
        if args.tools_command == "claim-builder":
            from .tools.claim_builder import build_claim

            build_claim(args.dir)
        else:
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
