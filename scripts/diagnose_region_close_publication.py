#!/usr/bin/env python3
"""Read-only C0 diagnosis for the numeric PNF region-close cascade."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect


CONTRACT = "sensiblaw.region-close-publication-diagnostic.v0_1"


def _fetchone(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return tuple(row) if row is not None else ()


def _fetchall(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[tuple[Any, ...], ...]:
    cursor.execute(query, params)
    return tuple(tuple(row) for row in cursor.fetchall())


def _operation_classes(function_definition: str) -> tuple[str, ...]:
    labels = (
        ("interface_aggregation", "semantic_pnf_interface_export"),
        ("child_interface_scanning", "semantic_pnf_region AS child"),
        ("demand_reconciliation", "semantic_pnf_demand"),
        ("hierarchy_propagation", "rebuild_numeric_pnf_parent_frontier"),
        ("recurrence_mention_derivation", "semantic_pnf_mention"),
        ("parent_closure", "closure_state"),
        ("global_lookup", "semantic_pnf_visible_lookup"),
        ("revision_publication", "graph_revision"),
    )
    return tuple(label for label, marker in labels if marker in function_definition)


def _statement_counts(function_definition: str) -> dict[str, int]:
    return {
        keyword: len(re.findall(rf"\b{keyword}\b", function_definition, re.IGNORECASE))
        for keyword in ("SELECT", "INSERT", "UPDATE", "DELETE", "PERFORM")
    }


def _referenced_tables(function_definition: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(
                re.findall(
                    r"semantic_pnf_[a-z0-9_]+|semantic_parser_[a-z0-9_]+",
                    function_definition,
                    re.IGNORECASE,
                )
            )
        )
    )


def _called_functions(function_definition: str) -> tuple[str, ...]:
    names = re.findall(
        r"execution\.([a-z0-9_]+)\s*\(", function_definition, re.IGNORECASE
    )
    return tuple(sorted({name for name in names if not name.startswith("semantic_")}))


def diagnose_region_close_publication(
    database_url: str,
    *,
    run_ref: str,
    region_id: int | None = None,
) -> dict[str, Any]:
    """Inspect one region and its update trigger graph in a read-only transaction."""

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                if region_id is None:
                    selected = _fetchone(
                        cursor,
                        """
                        SELECT region_id
                          FROM execution.semantic_pnf_region
                         WHERE run_ref = %s
                           AND region_kind = 1
                           AND closure_state = 2
                         ORDER BY region_id
                         LIMIT 1
                        """,
                        (run_ref,),
                    )
                    if not selected:
                        raise ValueError("no locally-closed sentence region found")
                    region_id = int(selected[0])

                region = _fetchone(
                    cursor,
                    """
                    SELECT region_id, run_ref, document_ref, region_kind,
                           start_char, end_char, sequence_no, parent_region_id,
                           closure_state, graph_revision, authored_boundary
                      FROM execution.semantic_pnf_region
                     WHERE region_id = %s AND run_ref = %s
                    """,
                    (region_id, run_ref),
                )
                if not region:
                    raise ValueError("selected region does not belong to run")

                child_metrics = _fetchone(
                    cursor,
                    """
                    WITH RECURSIVE descendants AS (
                        SELECT region_id, parent_region_id, closure_state
                          FROM execution.semantic_pnf_region
                         WHERE parent_region_id = %s
                        UNION ALL
                        SELECT child.region_id, child.parent_region_id,
                               child.closure_state
                          FROM execution.semantic_pnf_region AS child
                          JOIN descendants AS ancestor
                            ON child.parent_region_id = ancestor.region_id
                    ), child_interfaces AS (
                        SELECT interface.interface_id
                          FROM descendants
                          JOIN execution.semantic_pnf_interface AS interface
                            ON interface.region_id = descendants.region_id
                    )
                    SELECT count(*) AS descendant_count,
                           count(*) FILTER (WHERE descendants.closure_state IN (2,3)),
                           count(*) FILTER (WHERE descendants.closure_state = 1),
                           (SELECT count(*) FROM child_interfaces),
                           (SELECT count(*)
                              FROM execution.semantic_pnf_interface_export AS export
                              JOIN child_interfaces
                                ON child_interfaces.interface_id = export.interface_id),
                           (SELECT count(*)
                              FROM execution.semantic_pnf_demand AS demand
                             WHERE demand.source_region_id IN (
                                 SELECT region_id FROM descendants
                             )),
                           (SELECT count(*)
                              FROM execution.semantic_pnf_object AS object
                             WHERE object.region_id IN (
                                 SELECT region_id FROM descendants
                             )),
                           (SELECT count(*)
                              FROM execution.semantic_pnf_factor AS factor
                             WHERE factor.region_id IN (
                                 SELECT region_id FROM descendants
                             )),
                           (SELECT count(*)
                              FROM execution.semantic_pnf_interface_lookup AS lookup
                              JOIN child_interfaces
                                ON child_interfaces.interface_id = lookup.interface_id)
                      FROM descendants
                    """,
                    (region_id,),
                )
                interface_metrics = _fetchone(
                    cursor,
                    """
                    SELECT interface.interface_id,
                           count(DISTINCT export.target_id),
                           count(DISTINCT demand.demand_id),
                           interface.node_count,
                           interface.edge_count,
                           interface.unresolved_count,
                           interface.graph_revision
                      FROM execution.semantic_pnf_interface AS interface
                      LEFT JOIN execution.semantic_pnf_interface_export AS export
                        ON export.interface_id = interface.interface_id
                      LEFT JOIN execution.semantic_pnf_demand AS demand
                        ON demand.source_interface_id = interface.interface_id
                     WHERE interface.region_id = %s
                     GROUP BY interface.interface_id, interface.node_count,
                              interface.edge_count, interface.unresolved_count,
                              interface.graph_revision
                    """,
                    (region_id,),
                )
                depth = _fetchone(
                    cursor,
                    """
                    WITH RECURSIVE ancestors(region_id, parent_region_id, depth) AS (
                        SELECT region_id, parent_region_id, 0
                          FROM execution.semantic_pnf_region
                         WHERE region_id = %s
                        UNION ALL
                        SELECT parent.region_id, parent.parent_region_id,
                               ancestors.depth + 1
                          FROM execution.semantic_pnf_region AS parent
                          JOIN ancestors ON ancestors.parent_region_id = parent.region_id
                    )
                    SELECT max(depth), count(*) FROM ancestors
                    """,
                    (region_id,),
                )
                triggers = _fetchall(
                    cursor,
                    """
                    SELECT tg.tgname, pg_get_triggerdef(tg.oid), proc.proname,
                           pg_get_functiondef(proc.oid)
                      FROM pg_trigger AS tg
                      JOIN pg_class AS rel ON rel.oid = tg.tgrelid
                      JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace
                      JOIN pg_proc AS proc ON proc.oid = tg.tgfoid
                     WHERE ns.nspname = 'execution'
                       AND rel.relname = 'semantic_pnf_region'
                       AND NOT tg.tgisinternal
                     ORDER BY tg.tgname
                    """,
                    (),
                )
                trigger_receipts = [
                    {
                        "name": str(name),
                        "definition": str(definition),
                        "function_name": str(proname),
                        "definition_bytes": len(str(function).encode("utf-8")),
                        "definition_sha256": hashlib.sha256(
                            str(function).encode("utf-8")
                        ).hexdigest(),
                        "statement_counts": _statement_counts(str(function)),
                        "referenced_tables": list(_referenced_tables(str(function))),
                        "called_functions": list(_called_functions(str(function))),
                        "operation_classes": list(_operation_classes(str(function))),
                    }
                    for name, definition, proname, function in triggers
                ]
                update_plan = _fetchone(
                    cursor,
                    """
                    EXPLAIN (VERBOSE, COSTS, FORMAT JSON)
                    UPDATE execution.semantic_pnf_region
                       SET closure_state = 3,
                           graph_revision = graph_revision + 1
                     WHERE region_id = %s
                    """,
                    (region_id,),
                )
                sibling_plan = _fetchone(
                    cursor,
                    """
                    EXPLAIN (VERBOSE, COSTS, FORMAT JSON)
                    SELECT region_id, sequence_no, start_char, end_char
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s AND document_ref = %s
                       AND region_kind = %s
                       AND parent_region_id IS NOT DISTINCT FROM %s
                       AND closure_state IN (2, 3)
                       AND region_id <> %s
                       AND end_char <= %s
                     ORDER BY end_char DESC, sequence_no DESC, region_id DESC
                     LIMIT 1
                    """,
                    (region[1], region[2], region[3], region[7], region_id, region[4]),
                )
                return {
                    "contract": CONTRACT,
                    "run_ref": run_ref,
                    "selected_region_id": region_id,
                    "region": {
                        "region_id": int(region[0]),
                        "document_ref": str(region[2]),
                        "region_kind": int(region[3]),
                        "start_char": int(region[4]),
                        "end_char": int(region[5]),
                        "parent_region_id": int(region[7]) if region[7] is not None else None,
                        "closure_state": int(region[8]),
                        "graph_revision": int(region[9]),
                    },
                    "work_shape": {
                        "descendant_region_count": int(child_metrics[0]),
                        "closed_descendant_count": int(child_metrics[1]),
                        "open_descendant_count": int(child_metrics[2]),
                        "descendant_interface_count": int(child_metrics[3]),
                        "descendant_interface_export_count": int(child_metrics[4]),
                        "descendant_demand_count": int(child_metrics[5]),
                        "descendant_object_count": int(child_metrics[6]),
                        "descendant_factor_count": int(child_metrics[7]),
                        "descendant_lookup_count": int(child_metrics[8]),
                        "hierarchy_depth": int(depth[0]),
                        "ancestor_count": int(depth[1]),
                    },
                    "selected_interface": (
                        {
                            "interface_id": int(interface_metrics[0]),
                            "export_count": int(interface_metrics[1]),
                            "demand_count": int(interface_metrics[2]),
                            "node_count": int(interface_metrics[3]),
                            "edge_count": int(interface_metrics[4]),
                            "unresolved_count": int(interface_metrics[5]),
                            "graph_revision": int(interface_metrics[6]),
                        }
                        if interface_metrics
                        else None
                    ),
                    "trigger_graph": trigger_receipts,
                    "plans": {
                        "region_close_update": update_plan[0] if update_plan else None,
                        "nearest_closed_sibling": sibling_plan[0] if sibling_plan else None,
                        "analyze_executed": False,
                    },
                    "database_mutations_performed": False,
                    "provider_io_performed": False,
                }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--region-id", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = diagnose_region_close_publication(
        args.database_url, run_ref=args.run_ref, region_id=args.region_id
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
