#!/usr/bin/env python3
"""Two-phase minimal C3b canonical reducer certification harness.

The baseline phase must run on an isolated database migrated through C3a/C3
boundary transport (074/075) but *before* migration 076 replaces the canonical
parent reducer. It executes the normal streaming producer over a tiny authored
fixture, requires at least one paragraph interface, and records the strongest
paragraph as the legacy-authority oracle.

After migration 076 is applied to the same isolated database, the certify phase
runs the existing rollback-safe delta-fed reducer probe against that retained
legacy paragraph authority. No full corpus run is required and certification
never mutates the historical .env database.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_delta_fed_canonical_parent_reducer import (
    benchmark_delta_fed_canonical_parent_reducer,
)
from src.storage.postgres.spacy_parser_model import STREAMING_SPACY_CONTRACT
from src.storage.postgres.streaming_spacy_execution import run_streaming_spacy_execution
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.c3b-minimal-canonical-fixture.v0_1"
FIXTURE_TEXT = """The tenant must pay rent. The landlord may inspect the premises.

If rent is unpaid, the landlord may give notice. The tenant must leave after termination.
"""


def _reducer_is_delta_fed(cursor: Any) -> bool:
    cursor.execute(
        """
        SELECT pg_get_functiondef(
            'execution.rebuild_numeric_pnf_parent_frontier(bigint)'::regprocedure
        )
        """
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("canonical parent reducer function is missing")
    source = str(row[0]).casefold()
    return "semantic_pnf_parent_delta_projection" in source


def _boundary_transport_is_complete(cursor: Any) -> bool:
    cursor.execute(
        """
        SELECT to_regclass(
            'execution.semantic_pnf_parent_delta_projection'
        ) IS NOT NULL,
        to_regclass(
            'execution.semantic_pnf_parent_delta_lookup_projection'
        ) IS NOT NULL
        """
    )
    export_projection, lookup_projection = cursor.fetchone()
    return bool(export_projection and lookup_projection)


def _select_paragraph_oracle(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, int]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT region.region_id,
                           interface.interface_id,
                           count(DISTINCT child.region_id) AS child_count,
                           count(DISTINCT export.target_id) AS export_count,
                           count(DISTINCT lookup.target_id) AS lookup_count
                      FROM execution.semantic_pnf_region AS region
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.region_id = region.region_id
                      LEFT JOIN execution.semantic_pnf_region AS child
                        ON child.parent_region_id = region.region_id
                       AND child.region_kind <> 9
                      LEFT JOIN execution.semantic_pnf_parent_delta_projection AS export
                        ON export.parent_region_id = region.region_id
                      LEFT JOIN execution.semantic_pnf_parent_delta_lookup_projection AS lookup
                        ON lookup.parent_region_id = region.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                       AND region.region_kind = 3
                     GROUP BY region.region_id, interface.interface_id
                     ORDER BY export_count DESC,
                              lookup_count DESC,
                              child_count DESC,
                              region.region_id
                     LIMIT 1
                    """,
                    (run_ref, document_ref),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "minimal canonical producer did not create a paragraph interface"
                    )
                return {
                    "region_id": int(row[0]),
                    "interface_id": int(row[1]),
                    "child_count": int(row[2]),
                    "transported_export_count": int(row[3]),
                    "transported_lookup_count": int(row[4]),
                }
    finally:
        connection.close()


def create_legacy_baseline(
    database_url: str,
    *,
    fixture_id: str,
    artifact_root: Path,
) -> dict[str, Any]:
    run_ref = f"c3b-minimal-run:{fixture_id}"
    document_ref = f"c3b-minimal-document:{fixture_id}"

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                if not _boundary_transport_is_complete(cursor):
                    raise RuntimeError(
                        "C3b baseline requires migrations 074 and 075 before producer execution"
                    )
                if _reducer_is_delta_fed(cursor):
                    raise RuntimeError(
                        "C3b baseline must be produced before migration 076 replaces the reducer"
                    )
    finally:
        connection.close()

    run_streaming_spacy_execution(
        database_url=database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        canonical_text=FIXTURE_TEXT,
        parser_contract_ref=STREAMING_SPACY_CONTRACT,
        artifact_root=artifact_root,
        worker_count=1,
    )
    oracle = _select_paragraph_oracle(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    if oracle["child_count"] < 1:
        raise RuntimeError("selected paragraph oracle has no child fibres")

    return {
        "contract": CONTRACT,
        "phase": "baseline",
        "fixture_id": fixture_id,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "paragraph_oracle": oracle,
        "gates": {
            "legacy_reducer_used": True,
            "complete_boundary_transport_installed": True,
            "paragraph_interface_present": True,
        },
        "authority": {
            "baseline_requires_isolated_database": True,
            "migration_076_applied": False,
            "canonical_authority_promotion_claimed": False,
        },
    }


def certify_delta_fed_reducer(
    database_url: str,
    *,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    if baseline.get("contract") != CONTRACT or baseline.get("phase") != "baseline":
        raise ValueError("baseline receipt is not a C3b minimal baseline")
    run_ref = str(baseline["run_ref"])
    region_id = int(baseline["paragraph_oracle"]["region_id"])

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                if not _boundary_transport_is_complete(cursor):
                    raise RuntimeError("complete transported boundary is missing")
                if not _reducer_is_delta_fed(cursor):
                    raise RuntimeError(
                        "C3b certification requires migration 076 to be applied"
                    )
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_region AS region
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.region_id = region.region_id
                     WHERE region.region_id = %s
                       AND region.run_ref = %s
                       AND region.region_kind = 3
                    """,
                    (region_id, run_ref),
                )
                if int(cursor.fetchone()[0]) != 1:
                    raise RuntimeError("legacy paragraph oracle is missing after migration 076")
    finally:
        connection.close()

    probe = benchmark_delta_fed_canonical_parent_reducer(
        database_url,
        run_ref=run_ref,
        region_id=region_id,
    )
    return {
        "contract": CONTRACT,
        "phase": "certify",
        "fixture_id": baseline["fixture_id"],
        "run_ref": run_ref,
        "document_ref": baseline["document_ref"],
        "paragraph_oracle": baseline["paragraph_oracle"],
        "delta_fed_probe": probe,
        "gates": {
            "migration_076_applied": True,
            "boundary_parity_clean": (
                int(probe["boundary"]["missing_from_projection"]) == 0
                and int(probe["boundary"]["extra_in_projection"]) == 0
            ),
            "canonical_authority_parity": bool(probe["authority_parity"]["equal"]),
            "probe_rolled_back": bool(
                probe["authority"]["probe_transaction_rolled_back"]
            ),
            "zero_source_token_rescan": (
                int(probe["work_shape"]["source_token_rescan_count"]) == 0
            ),
        },
        "authority": {
            "canonical_authority_promotion_claimed": False,
            "certification_mutates_legacy_authority": False,
        },
    }


def _write_receipt(receipt: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if output is not None:
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="phase", required=True)

    baseline_parser = subparsers.add_parser("baseline")
    baseline_parser.add_argument("--database-url", required=True)
    baseline_parser.add_argument("--fixture-id", default="default")
    baseline_parser.add_argument("--artifact-root", type=Path, required=True)
    baseline_parser.add_argument("--output", type=Path, required=True)

    certify_parser = subparsers.add_parser("certify")
    certify_parser.add_argument("--database-url", required=True)
    certify_parser.add_argument("--baseline", type=Path, required=True)
    certify_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.phase == "baseline":
        receipt = create_legacy_baseline(
            args.database_url,
            fixture_id=args.fixture_id,
            artifact_root=args.artifact_root,
        )
        _write_receipt(receipt, args.output)
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    receipt = certify_delta_fed_reducer(args.database_url, baseline=baseline)
    _write_receipt(receipt, args.output)
    gates = receipt["gates"]
    return 0 if all(bool(value) for value in gates.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
