#!/usr/bin/env python3
"""Read-only B2 recursive boundary-delta transport certification.

The production delta triggers already apply to every interface export/lookup,
not only sentence interfaces.  Therefore paragraph outputs can become adaptive
or document inputs through the same physical transport law.  This benchmark
checks that law at every populated hierarchy hop without opening semantic
interiors.

For every parent region it verifies both:

  direct child boundary atoms == transported parent-addressed atoms

and the homomorphism/fusion form:

  transport(union child atoms) == union(transport child atoms).

Only region/interface topology and compact interface export/lookup boundaries
are read. Parser tokens, semantic objects, factors, hyperedges, demands, actor
profiles and global inventories are not source carriers for B2 transport.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.recursive-boundary-delta-transport.v0_1"
EXECUTION_WINDOW_KIND = 9
DOCUMENT_KIND = 10


def _rows(cursor: Any, sql: str, params: tuple[Any, ...]) -> frozenset[tuple[Any, ...]]:
    cursor.execute(sql, params)
    return frozenset(tuple(row) for row in cursor.fetchall())


def _parent_rows(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[tuple[int, int, int], ...]:
    cursor.execute(
        """
        SELECT DISTINCT parent.region_id,
               parent.region_kind,
               parent_interface.interface_id
          FROM execution.semantic_pnf_region AS parent
          JOIN execution.semantic_pnf_interface AS parent_interface
            ON parent_interface.region_id = parent.region_id
          JOIN execution.semantic_pnf_region AS child
            ON child.parent_region_id = parent.region_id
           AND child.region_kind <> %s
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child.region_id
         WHERE parent.run_ref = %s
           AND parent.document_ref = %s
         ORDER BY parent.region_kind, parent.region_id
        """,
        (EXECUTION_WINDOW_KIND, run_ref, document_ref),
    )
    return tuple((int(a), int(b), int(c)) for a, b, c in cursor.fetchall())


def _direct_exports(cursor: Any, parent_region_id: int) -> frozenset[tuple[Any, ...]]:
    return _rows(
        cursor,
        """
        SELECT child.region_id,
               child_interface.interface_id,
               export.export_kind,
               export.target_kind,
               export.target_id,
               export.key_symbol_id,
               export.role_symbol_id,
               export.residual_type_symbol_id,
               export.rank,
               export.promotion_score,
               export.scope_class,
               export.origin_interface_id,
               export.outward_required
          FROM execution.semantic_pnf_region AS child
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child.region_id
          JOIN execution.semantic_pnf_interface_export AS export
            ON export.interface_id = child_interface.interface_id
         WHERE child.parent_region_id = %s
           AND child.region_kind <> %s
        """,
        (parent_region_id, EXECUTION_WINDOW_KIND),
    )


def _projected_exports(cursor: Any, parent_region_id: int) -> frozenset[tuple[Any, ...]]:
    return _rows(
        cursor,
        """
        SELECT child_region_id,
               child_interface_id,
               export_kind,
               target_kind,
               target_id,
               key_symbol_id,
               role_symbol_id,
               residual_type_symbol_id,
               rank,
               promotion_score,
               scope_class,
               origin_interface_id,
               outward_required
          FROM execution.semantic_pnf_parent_delta_projection
         WHERE parent_region_id = %s
        """,
        (parent_region_id,),
    )


def _direct_lookups(cursor: Any, parent_region_id: int) -> frozenset[tuple[Any, ...]]:
    return _rows(
        cursor,
        """
        SELECT child.region_id,
               child_interface.interface_id,
               lookup.key_kind,
               lookup.key_a,
               lookup.key_b,
               lookup.target_kind,
               lookup.target_id,
               lookup.rank
          FROM execution.semantic_pnf_region AS child
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child.region_id
          JOIN execution.semantic_pnf_interface_lookup AS lookup
            ON lookup.interface_id = child_interface.interface_id
         WHERE child.parent_region_id = %s
           AND child.region_kind <> %s
        """,
        (parent_region_id, EXECUTION_WINDOW_KIND),
    )


def _projected_lookups(cursor: Any, parent_region_id: int) -> frozenset[tuple[Any, ...]]:
    return _rows(
        cursor,
        """
        SELECT child_region_id,
               child_interface_id,
               key_kind,
               key_a,
               key_b,
               target_kind,
               target_id,
               rank
          FROM execution.semantic_pnf_parent_delta_lookup_projection
         WHERE parent_region_id = %s
        """,
        (parent_region_id,),
    )


def _fuse_export_rows(rows: frozenset[tuple[Any, ...]]) -> frozenset[tuple[Any, ...]]:
    groups: dict[tuple[int, int, int], list[tuple[Any, ...]]] = {}
    for row in rows:
        # child region/interface are address provenance, not fused identity.
        key = (int(row[2]), int(row[3]), int(row[4]))
        groups.setdefault(key, []).append(row)
    fused: set[tuple[Any, ...]] = set()
    for (export_kind, target_kind, target_id), values in groups.items():
        key_symbols = [int(row[5]) for row in values if row[5] is not None]
        roles = [int(row[6]) for row in values if row[6] is not None]
        residuals = [int(row[7]) for row in values if row[7] is not None]
        origins = [
            int(row[11]) if row[11] is not None else int(row[1])
            for row in values
        ]
        fused.add(
            (
                export_kind,
                target_kind,
                target_id,
                min(key_symbols) if key_symbols else None,
                min(roles) if roles else None,
                min(residuals) if residuals else None,
                min(int(row[8]) for row in values),
                max(float(row[9]) for row in values),
                max(int(row[10]) for row in values),
                min(origins),
                any(bool(row[12]) for row in values),
                len(values),
            )
        )
    return frozenset(fused)


def _fused_export_view(cursor: Any, parent_region_id: int) -> frozenset[tuple[Any, ...]]:
    return _rows(
        cursor,
        """
        SELECT export_kind, target_kind, target_id,
               key_symbol_id, role_symbol_id, residual_type_symbol_id,
               rank, promotion_score, scope_class,
               origin_interface_id, outward_required,
               contributing_child_count
          FROM execution.semantic_pnf_parent_delta_fused_export
         WHERE parent_region_id = %s
        """,
        (parent_region_id,),
    )


def _fuse_lookup_rows(rows: frozenset[tuple[Any, ...]]) -> frozenset[tuple[Any, ...]]:
    groups: dict[tuple[int, int, int, int, int], list[tuple[Any, ...]]] = {}
    for row in rows:
        key = tuple(int(value) for value in row[2:7])
        groups.setdefault(key, []).append(row)
    return frozenset(
        (
            *key,
            min(int(row[7]) for row in values),
            len(values),
        )
        for key, values in groups.items()
    )


def _fused_lookup_view(cursor: Any, parent_region_id: int) -> frozenset[tuple[Any, ...]]:
    return _rows(
        cursor,
        """
        SELECT key_kind, key_a, key_b, target_kind, target_id,
               rank, contributing_child_count
          FROM execution.semantic_pnf_parent_delta_fused_lookup
         WHERE parent_region_id = %s
        """,
        (parent_region_id,),
    )


def benchmark_recursive_boundary_delta_transport(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, Any]:
    started = monotonic_ns()
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
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
                export_present, lookup_present = cursor.fetchone()
                if not bool(export_present and lookup_present):
                    raise RuntimeError("B2 requires the complete transported boundary")

                parents = _parent_rows(
                    cursor,
                    run_ref=run_ref,
                    document_ref=document_ref,
                )
                if not parents:
                    raise RuntimeError("B2 selected document has no populated parent fibres")

                mismatches: list[dict[str, Any]] = []
                hop_counter: Counter[str] = Counter()
                child_interface_hops = 0
                transported_export_atoms = 0
                transported_lookup_atoms = 0

                for parent_region_id, parent_kind, _parent_interface_id in parents:
                    cursor.execute(
                        """
                        SELECT child.region_kind, count(*)
                          FROM execution.semantic_pnf_region AS child
                          JOIN execution.semantic_pnf_interface AS child_interface
                            ON child_interface.region_id = child.region_id
                         WHERE child.parent_region_id = %s
                           AND child.region_kind <> %s
                         GROUP BY child.region_kind
                         ORDER BY child.region_kind
                        """,
                        (parent_region_id, EXECUTION_WINDOW_KIND),
                    )
                    for child_kind, count in cursor.fetchall():
                        hop_counter[f"{int(child_kind)}->{parent_kind}"] += int(count)
                        child_interface_hops += int(count)

                    direct_exports = _direct_exports(cursor, parent_region_id)
                    projected_exports = _projected_exports(cursor, parent_region_id)
                    direct_lookups = _direct_lookups(cursor, parent_region_id)
                    projected_lookups = _projected_lookups(cursor, parent_region_id)
                    transported_export_atoms += len(projected_exports)
                    transported_lookup_atoms += len(projected_lookups)

                    direct_fused_exports = _fuse_export_rows(direct_exports)
                    projected_fused_exports = _fused_export_view(cursor, parent_region_id)
                    direct_fused_lookups = _fuse_lookup_rows(direct_lookups)
                    projected_fused_lookups = _fused_lookup_view(cursor, parent_region_id)

                    export_missing = direct_exports - projected_exports
                    export_extra = projected_exports - direct_exports
                    lookup_missing = direct_lookups - projected_lookups
                    lookup_extra = projected_lookups - direct_lookups
                    fused_export_missing = direct_fused_exports - projected_fused_exports
                    fused_export_extra = projected_fused_exports - direct_fused_exports
                    fused_lookup_missing = direct_fused_lookups - projected_fused_lookups
                    fused_lookup_extra = projected_fused_lookups - direct_fused_lookups
                    if any(
                        (
                            export_missing,
                            export_extra,
                            lookup_missing,
                            lookup_extra,
                            fused_export_missing,
                            fused_export_extra,
                            fused_lookup_missing,
                            fused_lookup_extra,
                        )
                    ):
                        mismatches.append(
                            {
                                "parent_region_id": parent_region_id,
                                "parent_region_kind": parent_kind,
                                "export_missing": len(export_missing),
                                "export_extra": len(export_extra),
                                "lookup_missing": len(lookup_missing),
                                "lookup_extra": len(lookup_extra),
                                "fused_export_missing": len(fused_export_missing),
                                "fused_export_extra": len(fused_export_extra),
                                "fused_lookup_missing": len(fused_lookup_missing),
                                "fused_lookup_extra": len(fused_lookup_extra),
                            }
                        )

                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_global_lookup
                     WHERE run_ref = %s
                       AND document_ref = %s
                       AND region_kind <> %s
                    """,
                    (run_ref, document_ref, DOCUMENT_KIND),
                )
                non_root_global_rows = int(cursor.fetchone()[0])

                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_visible_lookup AS visible
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id = visible.interface_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                       AND region.region_kind <> %s
                    """,
                    (run_ref, document_ref, DOCUMENT_KIND),
                )
                non_root_visible_rows = int(cursor.fetchone()[0])
    finally:
        connection.close()

    elapsed_ns = monotonic_ns() - started
    parity_equal = not mismatches
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "parent_fibre_count": len(parents),
        "hierarchy_hops": dict(sorted(hop_counter.items())),
        "parity": {
            "exact_transport_equal": parity_equal,
            "fusion_naturality_equal": parity_equal,
            "mismatch_parent_count": len(mismatches),
            "first_mismatches": mismatches[:20],
        },
        "work": {
            "hierarchy_hop_count": child_interface_hops,
            "transported_export_atom_count": transported_export_atoms,
            "transported_lookup_atom_count": transported_lookup_atoms,
            "transported_delta_count": transported_export_atoms
            + transported_lookup_atoms,
            "fusion_input_count": transported_export_atoms + transported_lookup_atoms,
            "source_interior_rescan_count": 0,
            "global_lookup_per_hop_count": 0,
            "database_mutations_performed": False,
        },
        "root_authority": {
            "non_document_global_lookup_rows": non_root_global_rows,
            "non_document_visible_lookup_rows": non_root_visible_rows,
            "root_only_global_lookup": non_root_global_rows == 0,
            "root_only_visible_lookup": non_root_visible_rows == 0,
        },
        "timing_ns": {"recursive_boundary_certification": elapsed_ns},
        "authority": {
            "semantic_interior_tables_read": False,
            "independent_semantic_authority_created": False,
            "comparison_is_boundary_transport_only": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = benchmark_recursive_boundary_delta_transport(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    green = bool(
        receipt["parity"]["exact_transport_equal"]
        and receipt["parity"]["fusion_naturality_equal"]
        and receipt["work"]["source_interior_rescan_count"] == 0
        and receipt["root_authority"]["root_only_global_lookup"]
        and receipt["root_authority"]["root_only_visible_lookup"]
    )
    return 0 if green else 2


if __name__ == "__main__":
    raise SystemExit(main())
