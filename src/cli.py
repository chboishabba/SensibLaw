import argparse
import json
from datetime import datetime, date

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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
