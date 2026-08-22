"""Audit mask-0 sparse-frontier object demands before bounding their search.

The C2 experiment showed that constrained demand fibres are cheap and that the
measured adaptive interface is dominated by mask-0 object demands.  This probe
asks whether those rows are genuinely coordinate-free or merely lost projections
of producer-native evidence that still exists in exact provenance carriers.

It is read-only.  It does not infer a candidate, mutate a demand, or convert
missing provenance into negative evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-wildcard-provenance-diagnostic.v0_1"

_WILDCARD_DEMAND = """
SELECT demand.demand_id,
       demand.source_interface_id,
       demand.source_region_id,
       demand.source_start_char,
       demand.residual_type_symbol_id,
       demand.recency_class,
       demand.max_candidates,
       demand.source_object_id
  FROM execution.semantic_pnf_interface_export AS demand_export
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = demand_export.target_id
 WHERE demand_export.interface_id = %s
   AND demand_export.target_kind = 3
   AND demand.state IN (1, 3)
   AND demand.expected_target_kind = 1
   AND demand.expected_factor_type_symbol_id IS NULL
   AND demand.expected_object_kind_symbol_id IS NULL
   AND demand.role_symbol_id IS NULL
   AND demand.lexical_symbol_id IS NULL
"""


def _fetch_all(cursor: Any, sql: str, interface_id: int) -> list[tuple[Any, ...]]:
    cursor.execute(sql, (interface_id,) * sql.count("%s"))
    return list(cursor.fetchall())


def _summary_sql() -> str:
    return f"""
WITH wildcard AS MATERIALIZED ({_WILDCARD_DEMAND})
SELECT count(*)::BIGINT AS wildcard_demands,
       count(*) FILTER (WHERE source_interface_id IS NOT NULL)::BIGINT
           AS with_source_interface,
       count(*) FILTER (WHERE source_object_id IS NOT NULL)::BIGINT
           AS with_legacy_source_object,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_trigger_occurrence_v1 AS trigger
                WHERE trigger.demand_id = wildcard.demand_id
           )
       )::BIGINT AS with_exact_trigger_occurrence,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_target_occurrence_v1 AS target
                WHERE target.demand_id = wildcard.demand_id
           )
       )::BIGINT AS with_exact_target_occurrence,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_occurrence_provenance AS p
                WHERE p.demand_id = wildcard.demand_id
                  AND p.occurrence_role = 3
           )
       )::BIGINT AS with_exact_evidence_occurrence,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_occurrence_support AS support
                WHERE support.demand_id = wildcard.demand_id
                  AND support.support_kind IN (1, 2)
           )
       )::BIGINT AS with_legacy_strong_occurrence_support
  FROM wildcard
"""


def _residual_sql() -> str:
    return f"""
WITH wildcard AS MATERIALIZED ({_WILDCARD_DEMAND})
SELECT residual.symbol_text,
       region.region_kind,
       count(*)::BIGINT,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_trigger_occurrence_v1 AS trigger
                WHERE trigger.demand_id = wildcard.demand_id
           )
       )::BIGINT,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_target_occurrence_v1 AS target
                WHERE target.demand_id = wildcard.demand_id
           )
       )::BIGINT
  FROM wildcard
  JOIN execution.semantic_symbol AS residual
    ON residual.symbol_id = wildcard.residual_type_symbol_id
  JOIN execution.semantic_pnf_region AS region
    ON region.region_id = wildcard.source_region_id
 GROUP BY residual.symbol_text, region.region_kind
 ORDER BY count(*) DESC, residual.symbol_text, region.region_kind
"""


def _audit_sql() -> str:
    return f"""
WITH wildcard AS MATERIALIZED ({_WILDCARD_DEMAND})
SELECT audit.provenance_state,
       audit.has_explicit_target_rule,
       count(*)::BIGINT
  FROM wildcard
  JOIN execution.semantic_pnf_demand_occurrence_provenance_audit_v1 AS audit
    USING (demand_id)
 GROUP BY audit.provenance_state, audit.has_explicit_target_rule
 ORDER BY audit.provenance_state, audit.has_explicit_target_rule DESC
"""


def _recoverable_target_coordinate_sql() -> str:
    """Count exact coordinates exposed by already-registered target occurrences.

    These are diagnostics, not proposed automatic demand rewrites.  A target
    occurrence is producer-provenance evidence that lets us ask whether exact
    object kind / lexical coordinates still exist elsewhere in the authority
    graph even though the demand row itself is mask 0.
    """

    return f"""
WITH wildcard AS MATERIALIZED ({_WILDCARD_DEMAND}),
exact_target AS (
    SELECT wildcard.demand_id,
           target.token_id,
           target.object_id
      FROM wildcard
      JOIN execution.semantic_pnf_demand_target_occurrence_v1 AS target
        USING (demand_id)
),
coordinate AS (
    SELECT target.demand_id,
           object.object_kind_symbol_id,
           object.head_symbol_id,
           token.lemma_symbol_id
      FROM exact_target AS target
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = target.object_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id = target.token_id
)
SELECT count(*)::BIGINT AS exact_target_rows,
       count(*) FILTER (WHERE object_kind_symbol_id IS NOT NULL)::BIGINT
           AS with_object_kind,
       count(*) FILTER (WHERE head_symbol_id IS NOT NULL)::BIGINT
           AS with_object_head,
       count(*) FILTER (WHERE lemma_symbol_id IS NOT NULL)::BIGINT
           AS with_target_lemma,
       count(*) FILTER (
           WHERE head_symbol_id IS NOT NULL
             AND lemma_symbol_id IS NOT NULL
             AND head_symbol_id = lemma_symbol_id
       )::BIGINT AS head_equals_target_lemma
  FROM coordinate
"""


def _sample_sql(limit: int) -> str:
    return f"""
WITH wildcard AS MATERIALIZED ({_WILDCARD_DEMAND})
SELECT wildcard.demand_id,
       residual.symbol_text AS residual_type,
       region.region_kind,
       wildcard.source_interface_id,
       wildcard.source_region_id,
       wildcard.source_start_char,
       wildcard.recency_class,
       wildcard.max_candidates,
       wildcard.source_object_id,
       audit.provenance_state,
       audit.has_explicit_target_rule,
       trigger.producer_ref,
       trigger.token_id AS trigger_token_id,
       trigger_lemma.symbol_text AS trigger_lemma,
       target.token_id AS target_token_id,
       target.object_id AS target_object_id,
       target_lemma.symbol_text AS target_lemma,
       target_object.object_kind_symbol_id AS target_object_kind_symbol_id,
       target_object.head_symbol_id AS target_head_symbol_id
  FROM wildcard
  JOIN execution.semantic_symbol AS residual
    ON residual.symbol_id = wildcard.residual_type_symbol_id
  JOIN execution.semantic_pnf_region AS region
    ON region.region_id = wildcard.source_region_id
  LEFT JOIN execution.semantic_pnf_demand_occurrence_provenance_audit_v1 AS audit
    USING (demand_id)
  LEFT JOIN execution.semantic_pnf_demand_trigger_occurrence_v1 AS trigger
    USING (demand_id)
  LEFT JOIN execution.semantic_parser_token AS trigger_token
    ON trigger_token.token_id = trigger.token_id
  LEFT JOIN execution.semantic_symbol AS trigger_lemma
    ON trigger_lemma.symbol_id = trigger_token.lemma_symbol_id
  LEFT JOIN execution.semantic_pnf_demand_target_occurrence_v1 AS target
    USING (demand_id)
  LEFT JOIN execution.semantic_parser_token AS target_token
    ON target_token.token_id = target.token_id
  LEFT JOIN execution.semantic_symbol AS target_lemma
    ON target_lemma.symbol_id = target_token.lemma_symbol_id
  LEFT JOIN execution.semantic_pnf_object AS target_object
    ON target_object.object_id = target.object_id
 ORDER BY (target.token_id IS NOT NULL) DESC,
          (trigger.token_id IS NOT NULL) DESC,
          wildcard.demand_id
 LIMIT {int(limit)}
"""


def _single_row(cursor: Any, sql: str, interface_id: int) -> tuple[Any, ...]:
    rows = _fetch_all(cursor, sql, interface_id)
    if len(rows) != 1:
        raise RuntimeError(f"expected one diagnostic row, got {len(rows)}")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    with connect(args.database_url) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                summary = _single_row(cursor, _summary_sql(), args.interface_id)
                residual_rows = _fetch_all(cursor, _residual_sql(), args.interface_id)
                audit_rows = _fetch_all(cursor, _audit_sql(), args.interface_id)
                coordinate = _single_row(
                    cursor, _recoverable_target_coordinate_sql(), args.interface_id
                )
                sample_rows = _fetch_all(
                    cursor, _sample_sql(args.limit), args.interface_id
                )

    receipt = {
        "contract_ref": CONTRACT_REF,
        "interface_id": args.interface_id,
        "provider_io_performed": False,
        "semantic_mutation_performed": False,
        "summary": {
            "wildcard_demands": int(summary[0]),
            "with_source_interface": int(summary[1]),
            "with_legacy_source_object": int(summary[2]),
            "with_exact_trigger_occurrence": int(summary[3]),
            "with_exact_target_occurrence": int(summary[4]),
            "with_exact_evidence_occurrence": int(summary[5]),
            "with_legacy_strong_occurrence_support": int(summary[6]),
        },
        "residual_region_histogram": [
            {
                "residual_type": str(residual),
                "region_kind": int(region_kind),
                "demands": int(count),
                "with_trigger": int(with_trigger),
                "with_target": int(with_target),
            }
            for residual, region_kind, count, with_trigger, with_target in residual_rows
        ],
        "provenance_audit_histogram": [
            {
                "provenance_state": int(state),
                "has_explicit_target_rule": bool(has_rule),
                "demands": int(count),
            }
            for state, has_rule, count in audit_rows
        ],
        "exact_target_coordinate_inventory": {
            "exact_target_rows": int(coordinate[0]),
            "with_object_kind": int(coordinate[1]),
            "with_object_head": int(coordinate[2]),
            "with_target_lemma": int(coordinate[3]),
            "head_equals_target_lemma": int(coordinate[4]),
        },
        "sample": [
            {
                "demand_id": int(row[0]),
                "residual_type": str(row[1]),
                "region_kind": int(row[2]),
                "source_interface_id": int(row[3]) if row[3] is not None else None,
                "source_region_id": int(row[4]),
                "source_start_char": int(row[5]) if row[5] is not None else None,
                "recency_class": int(row[6]),
                "max_candidates": int(row[7]),
                "source_object_id": int(row[8]) if row[8] is not None else None,
                "provenance_state": int(row[9]) if row[9] is not None else None,
                "has_explicit_target_rule": bool(row[10]) if row[10] is not None else None,
                "producer_ref": str(row[11]) if row[11] is not None else None,
                "trigger_token_id": int(row[12]) if row[12] is not None else None,
                "trigger_lemma": str(row[13]) if row[13] is not None else None,
                "target_token_id": int(row[14]) if row[14] is not None else None,
                "target_object_id": int(row[15]) if row[15] is not None else None,
                "target_lemma": str(row[16]) if row[16] is not None else None,
                "target_object_kind_symbol_id": int(row[17]) if row[17] is not None else None,
                "target_head_symbol_id": int(row[18]) if row[18] is not None else None,
            }
            for row in sample_rows
        ],
    }

    encoded = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
