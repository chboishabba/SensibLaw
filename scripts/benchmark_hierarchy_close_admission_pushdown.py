from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.runtime.optimization_economy import concentration_profile
from src.storage.postgres.hierarchy_close_admission_pushdown import (
    CURRENT_GROUP_SELECT_SQL,
    PUSHDOWN_GROUP_SELECT_SQL,
    audit_parent_lookup_pushdown,
    child_interface_ids_for_parent,
)
from src.storage.postgres.spacy_parser_model import connect


def _closed_parent_interfaces(cursor: Any) -> tuple[int, ...]:
    cursor.execute(
        """
        SELECT parent_interface.interface_id
          FROM execution.semantic_pnf_interface AS parent_interface
          JOIN execution.semantic_pnf_region AS parent_region
            ON parent_region.region_id = parent_interface.region_id
         WHERE EXISTS (
             SELECT 1
               FROM execution.semantic_pnf_region AS child_region
               JOIN execution.semantic_pnf_interface AS child_interface
                 ON child_interface.region_id = child_region.region_id
              WHERE child_region.parent_region_id = parent_region.region_id
         )
         ORDER BY parent_region.start_char,
                  parent_region.end_char,
                  parent_region.region_id
        """
    )
    return tuple(int(row[0]) for row in cursor.fetchall())


def _explain_json(
    cursor: Any,
    *,
    sql: str,
    parameters: tuple[Any, ...],
    analyze: bool,
) -> Any:
    options = "ANALYZE, BUFFERS, FORMAT JSON" if analyze else "BUFFERS, FORMAT JSON"
    cursor.execute(f"EXPLAIN ({options}) {sql}", parameters)
    return cursor.fetchone()[0]


def build_report(
    database_url: str,
    *,
    explain_parent_interface_id: int | None = None,
    analyze: bool = False,
) -> dict[str, Any]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                parent_ids = _closed_parent_interfaces(cursor)
                audits = []
                for parent_interface_id in parent_ids:
                    children = child_interface_ids_for_parent(
                        cursor,
                        parent_interface_id=parent_interface_id,
                    )
                    if not children:
                        continue
                    audits.append(
                        audit_parent_lookup_pushdown(
                            cursor,
                            parent_interface_id=parent_interface_id,
                            child_interface_ids=children,
                        )
                    )

                source_work = [audit.source_rows for audit in audits]
                concentration = concentration_profile(source_work)
                report: dict[str, Any] = {
                    "parent_close_count": len(audits),
                    "exact_parity": all(audit.exact_parity for audit in audits),
                    "totals": {
                        "source_rows": sum(audit.source_rows for audit in audits),
                        "admitted_source_rows": sum(
                            audit.admitted_source_rows for audit in audits
                        ),
                        "grouped_candidate_rows": sum(
                            audit.grouped_candidate_rows for audit in audits
                        ),
                        "stored_parent_rows": sum(
                            audit.stored_parent_rows for audit in audits
                        ),
                        "missing_candidate_rows": sum(
                            audit.missing_candidate_rows for audit in audits
                        ),
                        "excess_candidate_rows": sum(
                            audit.excess_candidate_rows for audit in audits
                        ),
                    },
                    "concentration": [point.__dict__ for point in concentration],
                    "parents": [audit.to_dict() for audit in audits],
                }

                if explain_parent_interface_id is not None:
                    children = child_interface_ids_for_parent(
                        cursor,
                        parent_interface_id=explain_parent_interface_id,
                    )
                    if not children:
                        raise ValueError(
                            "requested EXPLAIN parent has no hierarchy child interfaces"
                        )
                    report["explain_parent_interface_id"] = explain_parent_interface_id
                    report["current_plan"] = _explain_json(
                        cursor,
                        sql=CURRENT_GROUP_SELECT_SQL,
                        parameters=(list(children),),
                        analyze=analyze,
                    )
                    report["pushdown_plan"] = _explain_json(
                        cursor,
                        sql=PUSHDOWN_GROUP_SELECT_SQL,
                        parameters=(
                            list(children),
                            int(explain_parent_interface_id),
                        ),
                        analyze=analyze,
                    )
                    report["analyze"] = analyze

                return report
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit hierarchy-close admission pushdown without authority writes."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--explain-parent-interface-id", type=int)
    parser.add_argument(
        "--analyze",
        action="store_true",
        help=(
            "Execute read-only grouping SELECTs under EXPLAIN ANALYZE. Prefer a "
            "disposable clone when measuring accepted performance evidence."
        ),
    )
    args = parser.parse_args()
    report = build_report(
        args.database_url,
        explain_parent_interface_id=args.explain_parent_interface_id,
        analyze=args.analyze,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
