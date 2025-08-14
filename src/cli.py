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

    query_parser = sub.add_parser(
        "query", help="Run a concept query over the knowledge base"
    )
    group = query_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Question or keyword query")
    group.add_argument(
        "--graph",
        type=Path,
        help="Path to a StoryGraph JSON file representing the query",
    )

    graph_parser = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    subgraph_parser = graph_sub.add_parser("subgraph", help="Extract subgraph")
    subgraph_parser.add_argument("--seed", required=True, help="Seed node identifier")
    subgraph_parser.add_argument("--hops", type=int, default=1, help="Number of hops")

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
        from .distinguish.loader import load_case_silhouette
        from .distinguish.engine import compare_story_to_case

        case_sil = load_case_silhouette(args.case)
        story_data = json.loads(args.story.read_text())
        story_tags = story_data.get("facts", {})
        result = compare_story_to_case(story_tags, case_sil)
        print(json.dumps(result))
    elif args.command == "query":
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
