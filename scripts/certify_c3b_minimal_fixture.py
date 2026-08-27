#!/usr/bin/env python3
"""Two-phase minimal delta-native hierarchy certification harness.

The baseline phase must run on an isolated database migrated through C3a/C3
boundary transport (074/075) but *before* migration 076 replaces the canonical
parent reducer. It executes the normal streaming producer over a tiny authored
fixture, requires at least one paragraph interface, records the strongest
paragraph as the legacy-authority oracle, and measures the legacy reducer in
rollback-only repetitions.

After migration 076 is applied to the same isolated database, the certify phase
uses that one oracle to close several independent gates at once:

* C3b: delta-fed canonical reducer semantic parity;
* C4: paired legacy-vs-delta-fed reducer timing on the same interface;
* B1.1: scoped A2 sentence->paragraph boundary-authority parity; and
* B2: recursive boundary transport/fusion parity across every populated hop.

Semantic parity, transport algebra, sparse authority, and physical performance
remain separately typed in the receipt. A speedup cannot manufacture semantic
correctness, and semantic parity does not imply a wall-clock win.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import sys
from time import monotonic_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_b1_1_a2_paragraph_authority_parity import (
    benchmark_b1_1_a2_paragraph_authority_parity,
)
from scripts.benchmark_delta_fed_canonical_parent_reducer import (
    benchmark_delta_fed_canonical_parent_reducer,
)
from scripts.benchmark_recursive_boundary_delta_transport import (
    benchmark_recursive_boundary_delta_transport,
)
from src.storage.postgres.spacy_parser_model import STREAMING_SPACY_CONTRACT
from src.storage.postgres.streaming_spacy_execution import run_streaming_spacy_execution
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.minimal-delta-native-hierarchy-certification.v0_3"
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


def _benchmark_current_reducer(
    database_url: str,
    *,
    interface_id: int,
    expect_delta_fed: bool,
    repetitions: int,
) -> dict[str, Any]:
    """Measure the installed reducer repeatedly; every repetition rolls back."""

    if repetitions < 1:
        raise ValueError("timing repetitions must be positive")
    samples: list[int] = []
    results: list[list[int]] = []
    for _ in range(repetitions):
        connection = connect(database_url)
        rolled_back = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '120s'")
                installed_delta_fed = _reducer_is_delta_fed(cursor)
                if installed_delta_fed is not expect_delta_fed:
                    expected = "delta-fed" if expect_delta_fed else "legacy"
                    raise RuntimeError(f"expected {expected} canonical reducer for timing")
                started = monotonic_ns()
                cursor.execute(
                    "SELECT * FROM execution.rebuild_numeric_pnf_parent_frontier(%s)",
                    (interface_id,),
                )
                row = cursor.fetchone()
                samples.append(monotonic_ns() - started)
                results.append([int(value) for value in row] if row is not None else [])
            connection.rollback()
            rolled_back = True
        finally:
            if not rolled_back:
                try:
                    connection.rollback()
                except Exception:
                    pass
            connection.close()
    ordered = sorted(samples)
    return {
        "repetitions": repetitions,
        "samples_ns": samples,
        "median_ns": int(median(samples)),
        "min_ns": ordered[0],
        "max_ns": ordered[-1],
        "reducer_results": results,
        "every_repetition_rolled_back": True,
        "delta_fed_reducer": expect_delta_fed,
    }


def create_legacy_baseline(
    database_url: str,
    *,
    fixture_id: str,
    artifact_root: Path,
    timing_repetitions: int = 3,
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

    legacy_timing = _benchmark_current_reducer(
        database_url,
        interface_id=oracle["interface_id"],
        expect_delta_fed=False,
        repetitions=timing_repetitions,
    )

    return {
        "contract": CONTRACT,
        "phase": "baseline",
        "fixture_id": fixture_id,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "paragraph_oracle": oracle,
        "performance": {"legacy_reducer": legacy_timing},
        "gates": {
            "legacy_reducer_used": True,
            "complete_boundary_transport_installed": True,
            "paragraph_interface_present": True,
        },
        "authority": {
            "baseline_requires_isolated_database": True,
            "migration_076_applied": False,
            "canonical_authority_promotion_claimed": False,
            "timing_repetitions_mutate_authority": False,
        },
    }


def certify_delta_fed_reducer(
    database_url: str,
    *,
    baseline: dict[str, Any],
    timing_repetitions: int = 3,
) -> dict[str, Any]:
    if baseline.get("contract") != CONTRACT or baseline.get("phase") != "baseline":
        raise ValueError("baseline receipt is not a minimal delta-native baseline")
    run_ref = str(baseline["run_ref"])
    document_ref = str(baseline["document_ref"])
    region_id = int(baseline["paragraph_oracle"]["region_id"])
    interface_id = int(baseline["paragraph_oracle"]["interface_id"])

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

    # C3b semantic parity remains the first gate. Everything below consumes the
    # same retained oracle but cannot turn a parity failure into success.
    probe = benchmark_delta_fed_canonical_parent_reducer(
        database_url,
        run_ref=run_ref,
        region_id=region_id,
    )
    delta_timing = _benchmark_current_reducer(
        database_url,
        interface_id=interface_id,
        expect_delta_fed=True,
        repetitions=timing_repetitions,
    )
    legacy_timing = baseline.get("performance", {}).get("legacy_reducer")
    if not isinstance(legacy_timing, dict) or "median_ns" not in legacy_timing:
        raise ValueError("baseline receipt is missing paired legacy timing")
    legacy_median = int(legacy_timing["median_ns"])
    delta_median = int(delta_timing["median_ns"])
    if legacy_median <= 0:
        raise ValueError("legacy reducer median must be positive")
    ratio = delta_median / legacy_median
    improvement_fraction = 1.0 - ratio

    # B1.1 is deliberately scoped to the A2-owned sentence boundary semantics,
    # not the whole reconciled paragraph frontier.
    b1_1 = benchmark_b1_1_a2_paragraph_authority_parity(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        limit_sentences=64,
    )

    # B2 checks the same transport/fusion law recursively for every populated
    # parent fibre and separately checks root-only lookup authority.
    b2 = benchmark_recursive_boundary_delta_transport(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )

    return {
        "contract": CONTRACT,
        "phase": "certify",
        "fixture_id": baseline["fixture_id"],
        "run_ref": run_ref,
        "document_ref": document_ref,
        "paragraph_oracle": baseline["paragraph_oracle"],
        "c3b": {"delta_fed_probe": probe},
        "c4_performance": {
            "legacy_reducer": legacy_timing,
            "delta_fed_reducer": delta_timing,
            "delta_to_legacy_ratio": ratio,
            "improvement_fraction": improvement_fraction,
            "delta_fed_faster": delta_median < legacy_median,
            "paired_same_region_interface": True,
            "performance_is_independent_of_semantic_parity": True,
        },
        "b1_1": b1_1,
        "b2": b2,
        "gates": {
            "migration_076_applied": True,
            "c3b_boundary_parity_clean": (
                int(probe["boundary"]["missing_from_projection"]) == 0
                and int(probe["boundary"]["extra_in_projection"]) == 0
            ),
            "c3b_canonical_authority_parity": bool(
                probe["authority_parity"]["equal"]
            ),
            "c3b_probe_rolled_back": bool(
                probe["authority"]["probe_transaction_rolled_back"]
            ),
            "c3b_zero_source_token_rescan": (
                int(probe["work_shape"]["source_token_rescan_count"]) == 0
            ),
            "b1_1_scoped_authority_parity": bool(b1_1["parity"]["equal"]),
            "b1_1_zero_source_interior_rescan": bool(
                b1_1["work"]["zero_source_interior_rescan"]
            ),
            "b2_exact_recursive_transport": bool(
                b2["parity"]["exact_transport_equal"]
            ),
            "b2_fusion_naturality": bool(
                b2["parity"]["fusion_naturality_equal"]
            ),
            "b2_zero_source_interior_rescan": (
                int(b2["work"]["source_interior_rescan_count"]) == 0
            ),
            "b2_root_only_global_lookup": bool(
                b2["root_authority"]["root_only_global_lookup"]
            ),
            "b2_root_only_visible_lookup": bool(
                b2["root_authority"]["root_only_visible_lookup"]
            ),
        },
        "authority": {
            "canonical_authority_promotion_claimed": False,
            "certification_mutates_legacy_authority": False,
            "b1_1_or_b2_create_independent_authority": False,
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
    baseline_parser.add_argument("--timing-repetitions", type=int, default=3)
    baseline_parser.add_argument("--output", type=Path, required=True)

    certify_parser = subparsers.add_parser("certify")
    certify_parser.add_argument("--database-url", required=True)
    certify_parser.add_argument("--baseline", type=Path, required=True)
    certify_parser.add_argument("--timing-repetitions", type=int, default=3)
    certify_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.phase == "baseline":
        receipt = create_legacy_baseline(
            args.database_url,
            fixture_id=args.fixture_id,
            artifact_root=args.artifact_root,
            timing_repetitions=args.timing_repetitions,
        )
        _write_receipt(receipt, args.output)
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    receipt = certify_delta_fed_reducer(
        args.database_url,
        baseline=baseline,
        timing_repetitions=args.timing_repetitions,
    )
    _write_receipt(receipt, args.output)
    gates = receipt["gates"]
    return 0 if all(bool(value) for value in gates.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
