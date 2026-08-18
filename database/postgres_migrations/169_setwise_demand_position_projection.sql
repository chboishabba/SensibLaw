BEGIN;

-- 169: source_start_char is an execution convenience, not semantic authority.
-- Migration 047 filled NULL from source_region.end_char with one BEFORE row
-- trigger per demand. Current sparse reducers already use the same COALESCE
-- fallback, but the retained compatibility planner still consumes the column
-- directly. Preserve compatibility without row-local work.
--
-- Producer-supplied positions remain authoritative for this execution coordinate;
-- only NULL positions are filled from the source-region boundary.

DROP TRIGGER IF EXISTS semantic_pnf_demand_position
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_inserted_demand_positions()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE execution.semantic_pnf_demand AS demand
       SET source_start_char=region.end_char
      FROM inserted_demand AS inserted
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=inserted.source_region_id
     WHERE demand.demand_id=inserted.demand_id
       AND inserted.source_start_char IS NULL
       AND demand.source_start_char IS NULL;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_position_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_inserted_demand_positions();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_updated_demand_positions()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS MATERIALIZED (
        SELECT current.demand_id,current.source_region_id,current.source_start_char
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.source_region_id IS DISTINCT FROM prior.source_region_id
            OR current.source_start_char IS DISTINCT FROM prior.source_start_char
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET source_start_char=region.end_char
      FROM changed
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=changed.source_region_id
     WHERE demand.demand_id=changed.demand_id
       AND changed.source_start_char IS NULL
       AND demand.source_start_char IS NULL;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_position_update_batch
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_updated_demand_positions();

-- Upgrade parity for rows that may have been loaded with triggers disabled.
UPDATE execution.semantic_pnf_demand AS demand
   SET source_start_char=region.end_char
  FROM execution.semantic_pnf_region AS region
 WHERE region.region_id=demand.source_region_id
   AND demand.source_start_char IS NULL;

COMMIT;
