from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.runtime.accepted_metric_ledger import build_accepted_metric_ledger
from src.storage.postgres.runtime_churn_audit import build_runtime_churn_audit


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the accepted spaCy-relative timing ledger and read-only PostgreSQL "
            "churn/query attribution for a strict numeric run."
        )
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--run-receipt",
        type=Path,
        help=(
            "Strict/numeric JSON receipt containing parser_receipt or compilation "
            "artifacts. If omitted, timing gate remains unknown."
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--query-limit", type=int, default=30)
    args = parser.parse_args()

    run = {} if args.run_receipt is None else _load_json(args.run_receipt)
    timing = build_accepted_metric_ledger(run).to_dict()
    churn = build_runtime_churn_audit(
        args.database_url,
        query_limit=max(1, int(args.query_limit)),
    )
    report = {
        "contract_ref": "sensiblaw.strict-numeric-runtime-attribution.v0_1",
        "accepted_metric": timing,
        "postgresql_churn": churn,
        "acceptance_semantics": (
            "database/runtime completion does not establish parser-relative performance; "
            "accepted_metric.gate must be pass for that claim"
        ),
    }
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output is None:
        print(encoded)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
