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

    # Tests evaluation command
    tests_parser = sub.add_parser(
        "tests", help="Evaluate legal test templates against facts"
    )
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser(
        "run", help="Evaluate a test template with provided facts"
    )
    tests_run.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Path to JSON template describing factors",
    )
    tests_run.add_argument(
        "--facts",
        type=Path,
        required=True,
        help="Path to JSON file mapping factors to evidence references",
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
    elif args.command == "tests":
        if args.tests_command == "run":
            from .tests.evaluator import evaluate

            template_data = json.loads(args.template.read_text())
            facts_data = json.loads(args.facts.read_text())
            table = evaluate(template_data, facts_data)
            print(json.dumps(table.to_json()))
        else:
            tests_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
