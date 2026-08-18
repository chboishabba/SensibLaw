BEGIN;

-- 160: source_object_id is a weak structural fast-path, not identity authority.
-- Migration 090a maintained it with one source-region object scan per demand and
-- unconditionally recomputed it from (source_region_id, lexical_symbol_id).
--
-- Two corrections are required for strict numeric production:
--
-- 1. project the weak lexical anchor for the whole affected demand relation;
-- 2. do not erase a stronger producer-native source_object_id merely because
--    lexical_symbol_id is NULL. A supplied object is retained only when it is an
--    active object in the exact source region. Otherwise lexical recovery is
--    attempted, and ambiguity/no match remains NULL.
--
-- This column remains explicitly non-authoritative. Exact occurrence provenance
-- and proof-relevant target selection continue to live in their dedicated
-- carriers.

DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_demand_source_objects_inserted()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH demand_input AS MATERIALIZED (
        SELECT demand.demand_id,
               demand.source_region_id,
               demand.lexical_symbol_id,
               demand.source_object_id,
               CASE
                 WHEN supplied.object_id IS NOT NULL THEN supplied.object_id
                 ELSE NULL
               END AS valid_supplied_object_id
          FROM inserted_demand AS demand
          LEFT JOIN execution.semantic_pnf_object AS supplied
            ON supplied.object_id=demand.source_object_id
           AND supplied.region_id=demand.source_region_id
           AND supplied.active
    ), lexical_match AS MATERIALIZED (
        SELECT demand.demand_id,
               count(object.object_id)::BIGINT AS match_count,
               min(object.object_id) AS matched_object_id
          FROM demand_input AS demand
          LEFT JOIN execution.semantic_pnf_object AS object
            ON demand.valid_supplied_object_id IS NULL
           AND demand.lexical_symbol_id IS NOT NULL
           AND object.region_id=demand.source_region_id
           AND object.head_symbol_id=demand.lexical_symbol_id
           AND object.active
         GROUP BY demand.demand_id
    ), resolved AS (
        SELECT demand.demand_id,
               COALESCE(
                   demand.valid_supplied_object_id,
                   CASE
                     WHEN lexical_match.match_count=1
                     THEN lexical_match.matched_object_id
                     ELSE NULL
                   END
               ) AS resolved_object_id
          FROM demand_input AS demand
          JOIN lexical_match USING(demand_id)
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET source_object_id=resolved.resolved_object_id
      FROM resolved
     WHERE demand.demand_id=resolved.demand_id
       AND demand.source_object_id IS DISTINCT FROM resolved.resolved_object_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor_insert
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_source_object_anchor_insert
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_demand_source_objects_inserted();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_demand_source_objects_updated()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS MATERIALIZED (
        SELECT current.demand_id,
               current.source_region_id,
               current.lexical_symbol_id,
               current.source_object_id
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.source_region_id IS DISTINCT FROM prior.source_region_id
            OR current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
            OR current.source_object_id IS DISTINCT FROM prior.source_object_id
    ), demand_input AS MATERIALIZED (
        SELECT demand.demand_id,
               demand.source_region_id,
               demand.lexical_symbol_id,
               demand.source_object_id,
               CASE
                 WHEN supplied.object_id IS NOT NULL THEN supplied.object_id
                 ELSE NULL
               END AS valid_supplied_object_id
          FROM changed AS demand
          LEFT JOIN execution.semantic_pnf_object AS supplied
            ON supplied.object_id=demand.source_object_id
           AND supplied.region_id=demand.source_region_id
           AND supplied.active
    ), lexical_match AS MATERIALIZED (
        SELECT demand.demand_id,
               count(object.object_id)::BIGINT AS match_count,
               min(object.object_id) AS matched_object_id
          FROM demand_input AS demand
          LEFT JOIN execution.semantic_pnf_object AS object
            ON demand.valid_supplied_object_id IS NULL
           AND demand.lexical_symbol_id IS NOT NULL
           AND object.region_id=demand.source_region_id
           AND object.head_symbol_id=demand.lexical_symbol_id
           AND object.active
         GROUP BY demand.demand_id
    ), resolved AS (
        SELECT demand.demand_id,
               COALESCE(
                   demand.valid_supplied_object_id,
                   CASE
                     WHEN lexical_match.match_count=1
                     THEN lexical_match.matched_object_id
                     ELSE NULL
                   END
               ) AS resolved_object_id
          FROM demand_input AS demand
          JOIN lexical_match USING(demand_id)
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET source_object_id=resolved.resolved_object_id
      FROM resolved
     WHERE demand.demand_id=resolved.demand_id
       AND demand.source_object_id IS DISTINCT FROM resolved.resolved_object_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor_update
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_source_object_anchor_update
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_demand_source_objects_updated();

COMMIT;
