#!/usr/bin/env python3
"""Plan or execute bounded Wikidata/Wiktionary enrichment over open PNF demands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.external_enrichment import (  # noqa: E402
    EnrichmentResult,
    ExternalLookupDemand,
)
from src.ontology.wikimedia_providers import (  # noqa: E402
    WikidataProvider,
    WikimediaMicrobatchRunner,
    WiktionaryProvider,
)
from src.pnf.external_enrichment_projection import (  # noqa: E402
    project_external_lookup_demands,
    summarize_external_lookup_plan,
)
from src.storage.postgres import PostgresCompilerStore  # noqa: E402
from src.storage.postgres.enrichment_planner import (  # noqa: E402
    load_external_lookup_demands,
)
from src.storage.postgres.enrichment_store import (  # noqa: E402
    persist_external_enrichment_results,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Compilation/artifact JSON")
    source.add_argument(
        "--corpus-ref",
        help="Load open external-evidence demands directly from PostgreSQL",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--plan-limit", type=int, default=1_000)
    parser.add_argument("--no-wiktionary", action="store_true")
    parser.add_argument("--microbatch-size", type=int, default=16)
    parser.add_argument("--request-budget-per-provider", type=int, default=64)
    parser.add_argument("--candidate-limit", type=int, default=5)
    return parser.parse_args()


def _artifact_rows(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        artifacts = value.get("artifacts")
        if isinstance(artifacts, Mapping):
            yield artifacts
        if "resolution_demands" in value and (
            "pnf_graph" in value or "refined_pnf_graph" in value
        ):
            yield value
        for key in ("compilations", "documents", "results"):
            rows = value.get(key)
            if isinstance(rows, list):
                for row in rows:
                    yield from _artifact_rows(row)
    elif isinstance(value, list):
        for row in value:
            yield from _artifact_rows(row)


def _artifact_demands(
    input_path: Path,
    *,
    include_wiktionary: bool,
) -> tuple[ExternalLookupDemand, ...]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    artifacts = tuple(_artifact_rows(payload))
    if not artifacts:
        raise SystemExit("input does not contain compiler artifacts")
    return tuple(
        demand
        for artifact in artifacts
        for demand in project_external_lookup_demands(
            artifact,
            include_wiktionary=include_wiktionary,
        )
    )


def _serialize_results(results: Iterable[EnrichmentResult]) -> list[dict[str, Any]]:
    return [row.to_dict() for row in results]


def main() -> int:
    args = _parse_args()
    include_wiktionary = not args.no_wiktionary
    store: PostgresCompilerStore | None = None
    try:
        if args.corpus_ref:
            if not args.database_url:
                raise SystemExit("--corpus-ref requires --database-url or DATABASE_URL")
            store = PostgresCompilerStore.connect(args.database_url)
            with store.transaction() as cursor:
                demands = load_external_lookup_demands(
                    cursor,
                    corpus_ref=args.corpus_ref,
                    limit=args.plan_limit,
                    include_wiktionary=include_wiktionary,
                )
            plan_source = "postgres_open_demands"
        else:
            demands = _artifact_demands(
                args.input,
                include_wiktionary=include_wiktionary,
            )
            plan_source = "compiler_artifact"

        plan = summarize_external_lookup_plan(demands)
        plan["plan_source"] = plan_source
        if args.corpus_ref:
            plan["corpus_ref"] = args.corpus_ref
        output: dict[str, Any] = {
            "schema_version": "sl.wikimedia_enrichment_run.v0_2",
            "plan": plan,
            "demands": [row.to_dict() for row in demands],
            "network_performed": False,
            "persisted": False,
            "authority": "candidate_only",
        }
        if not args.plan_only and demands:
            providers = [
                WikidataProvider(candidate_limit=args.candidate_limit),
            ]
            if include_wiktionary:
                providers.append(WiktionaryProvider())
            runner = WikimediaMicrobatchRunner(
                providers,
                microbatch_size=args.microbatch_size,
                request_budget_per_provider=args.request_budget_per_provider,
            )
            results = runner.run(demands)
            output["results"] = _serialize_results(results)
            output["network_performed"] = True
            output["summary"] = {
                "result_count": len(results),
                "candidate_set_count": sum(
                    len(row.candidate_sets) for row in results
                ),
                "candidate_count": sum(
                    len(candidate_set.candidates)
                    for row in results
                    for candidate_set in row.candidate_sets
                ),
                "monotone_pressure_receipt_count": sum(
                    receipt.monotone
                    for row in results
                    for receipt in row.pressure_receipts
                ),
                "nonmonotone_pressure_receipt_count": sum(
                    not receipt.monotone
                    for row in results
                    for receipt in row.pressure_receipts
                ),
                "identity_closure_count": 0,
            }
            if args.database_url:
                if store is None:
                    store = PostgresCompilerStore.connect(args.database_url)
                with store.transaction() as cursor:
                    persisted = persist_external_enrichment_results(cursor, results)
                output["persisted_candidate_set_refs"] = list(persisted)
                output["persisted"] = True
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
        print(encoded)
        return 0
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
