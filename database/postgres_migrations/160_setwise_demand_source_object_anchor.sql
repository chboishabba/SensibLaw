BEGIN;

-- 160: source_object_id is a weak structural fast-path, not identity authority.
-- Migration 090a maintained it with one source-region object scan per demand and
-- unconditionally recomputed it from (source_region_id, lexical_symbol_id).
--
-- Two corrections are required for strict numeric production:
--
-- 1. project the weak lexical anchor for the whole inserted demand relation;
-- 2. do not erase a stronger producer-native source_object_id merely because
--    lexical_symbol_id is NULL. A supplied object is retained only when it is an
--    active object in the exact source region. Otherwise lexical recovery is
--    attempted, and ambiguity/no match remains NULL.
--
-- INSERT remains set-wise because that is the production publication path.
-- UPDATE maintenance is deliberately different: PostgreSQL does not permit an
-- UPDATE OF column list together with transition relations, so a statement-level
-- transition trigger would wake on unrelated demand repairs.  Worse, its own
-- corrective UPDATE of source_object_id re-enters every UPDATE projection on
-- semantic_pnf_demand.  Normalize the three actual source-anchor coordinates in
-- a BEFORE-row trigger instead.  The row is written once, unrelated UPDATEs do
-- not wake this projection, and there is no self-update recursion.
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

-- Canonicalize one updated demand before it is written.  This function does not
-- UPDATE semantic_pnf_demand: it only rewrites NEW.source_object_id.  Therefore
-- the set-wise INSERT projection above may set source_object_id and pass through
-- this normalizer once without causing a second statement-level projection.
CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_demand_source_object()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    resolved_object_id BIGINT;
    lexical_match_count BIGINT := 0;
    lexical_matched_object_id BIGINT;
BEGIN
    IF NEW.source_object_id IS NOT NULL THEN
        SELECT object.object_id
          INTO resolved_object_id
          FROM execution.semantic_pnf_object AS object
         WHERE object.object_id=NEW.source_object_id
           AND object.region_id=NEW.source_region_id
           AND object.active;
    END IF;

    IF resolved_object_id IS NULL AND NEW.lexical_symbol_id IS NOT NULL THEN
        SELECT count(object.object_id)::BIGINT,
               min(object.object_id)
          INTO lexical_match_count,
               lexical_matched_object_id
          FROM execution.semantic_pnf_object AS object
         WHERE object.region_id=NEW.source_region_id
           AND object.head_symbol_id=NEW.lexical_symbol_id
           AND object.active;

        IF lexical_match_count=1 THEN
            resolved_object_id := lexical_matched_object_id;
        END IF;
    END IF;

    NEW.source_object_id := resolved_object_id;
    RETURN NEW;
END;
$$;

-- Drop the historical statement-level UPDATE spelling before installing the
-- dependency-indexed BEFORE-row normalizer.  This also makes migration replay
-- safe if an earlier draft of 160 was applied manually.
DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor_update
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor_update_before
    ON execution.semantic_pnf_demand;

CREATE TRIGGER semantic_pnf_demand_source_object_anchor_update_before
BEFORE UPDATE OF source_region_id, lexical_symbol_id, source_object_id
ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (
    NEW.source_region_id IS DISTINCT FROM OLD.source_region_id
    OR NEW.lexical_symbol_id IS DISTINCT FROM OLD.lexical_symbol_id
    OR NEW.source_object_id IS DISTINCT FROM OLD.source_object_id
)
EXECUTE FUNCTION execution.normalize_numeric_pnf_demand_source_object();

COMMIT;
