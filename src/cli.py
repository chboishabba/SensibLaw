import argparse
import json
from datetime import datetime, date

from .storage import VersionedStore
from .austlii_client import AustLIIClient
from .ingestion.austlii_adapter import AustLIIActAdapter


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

    aust_parser = sub.add_parser(
        "austlii-fetch", help="Fetch sections from AustLII and store them"
    )
    aust_parser.add_argument("--db", default="data/store.db", help="Path to database")
    aust_parser.add_argument("--act", required=True, help="Base URL of the Act")
    aust_parser.add_argument(
        "--sections", required=True, help="Comma separated section identifiers"
    )

    view_parser = sub.add_parser(
        "view", help="View stored section by canonical identifier"
    )
    view_parser.add_argument("--db", default="data/store.db", help="Path to database")
    view_parser.add_argument("--id", required=True, help="Canonical ID")

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
    elif args.command == "austlii-fetch":
        sections = [s.strip() for s in args.sections.split(",") if s.strip()]
        store = VersionedStore(args.db)
        client = AustLIIClient()
        adapter = AustLIIActAdapter(client, store)
        ids = adapter.fetch_act(args.act.rstrip("/"), sections)
        print(json.dumps(ids))
        store.close()
    elif args.command == "view":
        store = VersionedStore(args.db)
        doc = store.get_by_canonical_id(args.id)
        if doc is None:
            print("Not found")
        else:
            from .rules.extractor import extract_rules

            rules = [r.__dict__ for r in extract_rules(doc.body)]
            output = {
                "text": doc.body,
                "rules": rules,
                "provenance": doc.metadata.provenance,
                "ontology_tags": doc.metadata.ontology_tags,
            }
            print(json.dumps(output))
        store.close()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
