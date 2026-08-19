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

-- Canonicalize one updated demand before it is written. This retains the
-- producer-authored position when present, and fills only a NULL compatibility
-- coordinate from its exact source-region boundary. It never UPDATEs
-- semantic_pnf_demand, so it cannot re-enter demand projections.
CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_demand_position()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_start_char IS NULL THEN
        SELECT region.end_char
          INTO NEW.source_start_char
          FROM execution.semantic_pnf_region AS region
         WHERE region.region_id=NEW.source_region_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_position_update_batch
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_demand_position_update_before
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_position_update_before
BEFORE UPDATE OF source_region_id, source_start_char
ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (
    NEW.source_region_id IS DISTINCT FROM OLD.source_region_id
    OR NEW.source_start_char IS DISTINCT FROM OLD.source_start_char
)
EXECUTE FUNCTION execution.normalize_numeric_pnf_demand_position();

-- Upgrade parity for rows that may have been loaded with triggers disabled.
UPDATE execution.semantic_pnf_demand AS demand
   SET source_start_char=region.end_char
  FROM execution.semantic_pnf_region AS region
 WHERE region.region_id=demand.source_region_id
   AND demand.source_start_char IS NULL;

COMMIT;
