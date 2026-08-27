#!/usr/bin/env python3
"""Rollback-safe C3 parity/performance probe for one canonical parent reducer.

The retained canonical parent state is snapshotted first.  The C3 delta-fed
reducer is then executed inside the same transaction and every authoritative
parent-local surface is compared with that snapshot.  The transaction is
always rolled back, so certification cannot alter the retained fixture.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.delta-fed-canonical-parent-reducer.v0_1"


def _rows(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[tuple[Any, ...], ...]:
    cursor.execute(query, params)
    return tuple(tuple(row) for row in cursor.fetchall())


def _snapshot(cursor: Any, *, region_id: int, interface_id: int) -> dict[str, tuple[tuple[Any, ...], ...]]:
    demand_ids = tuple(
        int(row[0])
        for row in _rows(
            cursor,
            """
            SELECT DISTINCT target_id
              FROM execution.semantic_pnf_parent_delta_projection
             WHERE parent_region_id = %s AND target_kind = 3
             ORDER BY target_id
            """,
            (region_id,),
        )
    )
    demand_param = list(demand_ids) if demand_ids else [-1]
    return {
        "exports": _rows(
            cursor,
            """
            SELECT export_kind, target_kind, target_id,
                   key_symbol_id, role_symbol_id, residual_type_symbol_id,
                   rank, promotion_score, scope_class,
                   origin_interface_id, outward_required
              FROM execution.semantic_pnf_interface_export
             WHERE interface_id = %s
             ORDER BY export_kind, target_kind, target_id
            """,
            (interface_id,),
        ),
        "lookups": _rows(
            cursor,
            """
            SELECT key_kind, key_a, key_b, target_kind, target_id, rank
              FROM execution.semantic_pnf_interface_lookup
             WHERE interface_id = %s
             ORDER BY key_kind, key_a, key_b, target_kind, target_id
            """,
            (interface_id,),
        ),
        "actors": _rows(
            cursor,
            """
            SELECT object_id, object_kind_symbol_id, role_symbol_id,
                   factor_type_symbol_id, predicate_symbol_id,
                   occurrence_count, first_start_char, last_end_char,
                   promotion_score
              FROM execution.semantic_pnf_actor_profile
             WHERE interface_id = %s
             ORDER BY object_id, role_symbol_id,
                      factor_type_symbol_id, predicate_symbol_id
            """,
            (interface_id,),
        ),
        "resolutions": _rows(
            cursor,
            """
            SELECT demand_id, outcome_state, candidate_count,
                   selected_target_kind, selected_target_id, witness_interface_id
              FROM execution.semantic_pnf_frontier_resolution
             WHERE interface_id = %s
             ORDER BY demand_id
            """,
            (interface_id,),
        ),
        "demands": _rows(
            cursor,
            """
            SELECT demand_id, state, candidate_count,
                   resolved_target_kind, resolved_target_id
              FROM execution.semantic_pnf_demand
             WHERE demand_id = ANY(%s)
             ORDER BY demand_id
            """,
            (demand_param,),
        ),
        "candidates": _rows(
            cursor,
            """
            SELECT demand_id, ordinal, target_kind, target_id,
                   source_interface_id, ancestor_distance,
                   index_rank, candidate_score,
                   common_scope_interface_id, validation_state
              FROM execution.semantic_pnf_demand_candidate
             WHERE demand_id = ANY(%s)
             ORDER BY demand_id, ordinal, target_kind, target_id
            """,
            (demand_param,),
        ),
    }


def benchmark_delta_fed_canonical_parent_reducer(
    database_url: str,
    *,
    run_ref: str,
    region_id: int,
) -> dict[str, Any]:
    connection = connect(database_url)
    rolled_back = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            cursor.execute(
                """
                SELECT interface.interface_id, region.document_ref, region.region_kind
                  FROM execution.semantic_pnf_region AS region
                  JOIN execution.semantic_pnf_interface AS interface
                    ON interface.region_id = region.region_id
                 WHERE region.region_id = %s AND region.run_ref = %s
                """,
                (region_id, run_ref),
            )
            selected = cursor.fetchone()
            if selected is None:
                raise ValueError("selected parent region/interface not found")
            interface_id = int(selected[0])
            document_ref = str(selected[1])
            region_kind = int(selected[2])
            if region_kind == 1:
                raise ValueError("C3 parent probe requires a non-sentence region")

            cursor.execute(
                "SELECT * FROM execution.check_numeric_pnf_parent_boundary_parity(%s)",
                (region_id,),
            )
            direct_count, projected_count, missing, extra = (
                int(value) for value in cursor.fetchone()
            )
            if missing or extra:
                raise RuntimeError(
                    "transported export boundary is not parity-clean: "
                    f"missing={missing} extra={extra}"
                )

            before = _snapshot(cursor, region_id=region_id, interface_id=interface_id)
            started = monotonic_ns()
            cursor.execute(
                "SELECT * FROM execution.rebuild_numeric_pnf_parent_frontier(%s)",
                (interface_id,),
            )
            reducer_result = tuple(cursor.fetchone())
            reducer_ns = monotonic_ns() - started
            after = _snapshot(cursor, region_id=region_id, interface_id=interface_id)

            mismatches = {
                name: before[name] != after[name]
                for name in before
            }
            mismatch_names = [name for name, mismatch in mismatches.items() if mismatch]
            receipt = {
                "contract": CONTRACT,
                "run_ref": run_ref,
                "document_ref": document_ref,
                "region_id": region_id,
                "interface_id": interface_id,
                "region_kind": region_kind,
                "boundary": {
                    "direct_export_atom_count": direct_count,
                    "projected_export_atom_count": projected_count,
                    "missing_from_projection": missing,
                    "extra_in_projection": extra,
                },
                "authority_parity": {
                    "equal": not mismatch_names,
                    "mismatch_surfaces": mismatch_names,
                    "surface_counts_before": {
                        name: len(rows) for name, rows in before.items()
                    },
                    "surface_counts_after": {
                        name: len(rows) for name, rows in after.items()
                    },
                },
                "reducer_result": [int(value) for value in reducer_result],
                "timing_ns": {"delta_fed_parent_reducer": reducer_ns},
                "work_shape": {
                    "source_token_rescan_count": 0,
                    "transported_export_boundary_used": True,
                    "transported_lookup_boundary_used": True,
                },
                "authority": {
                    "probe_transaction_rolled_back": True,
                    "canonical_authority_promotion_claimed": False,
                },
            }
        connection.rollback()
        rolled_back = True
        return receipt
    finally:
        if not rolled_back:
            try:
                connection.rollback()
            except Exception:
                pass
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--region-id", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = benchmark_delta_fed_canonical_parent_reducer(
        args.database_url,
        run_ref=args.run_ref,
        region_id=args.region_id,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["authority_parity"]["equal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
