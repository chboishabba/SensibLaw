BEGIN;

ALTER TABLE execution.semantic_pnf_demand_candidate
    ADD COLUMN IF NOT EXISTS common_scope_interface_id BIGINT
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS validation_state SMALLINT NOT NULL DEFAULT 1
        CHECK (validation_state IN (1, 2, 3));

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_candidate_scope_idx
    ON execution.semantic_pnf_demand_candidate
       (common_scope_interface_id, validation_state, demand_id, ordinal);

CREATE OR REPLACE FUNCTION execution.nearest_common_pnf_interface(
    left_interface_id BIGINT,
    right_interface_id BIGINT
)
RETURNS BIGINT
LANGUAGE sql
STABLE
STRICT
AS $$
    WITH RECURSIVE
    left_chain(interface_id, parent_interface_id, depth) AS (
        SELECT interface_id, parent_interface_id, 0::BIGINT
          FROM execution.semantic_pnf_interface
         WHERE interface_id = left_interface_id
        UNION ALL
        SELECT parent.interface_id,
               parent.parent_interface_id,
               left_chain.depth + 1
          FROM left_chain
          JOIN execution.semantic_pnf_interface AS parent
            ON parent.interface_id = left_chain.parent_interface_id
    ),
    right_chain(interface_id, parent_interface_id, depth) AS (
        SELECT interface_id, parent_interface_id, 0::BIGINT
          FROM execution.semantic_pnf_interface
         WHERE interface_id = right_interface_id
        UNION ALL
        SELECT parent.interface_id,
               parent.parent_interface_id,
               right_chain.depth + 1
          FROM right_chain
          JOIN execution.semantic_pnf_interface AS parent
            ON parent.interface_id = right_chain.parent_interface_id
    )
    SELECT left_chain.interface_id
      FROM left_chain
      JOIN right_chain USING (interface_id)
     ORDER BY left_chain.depth + right_chain.depth,
              left_chain.interface_id
     LIMIT 1
$$;

CREATE OR REPLACE FUNCTION execution.validate_numeric_pnf_demand_candidate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    demand_row RECORD;
    source_region RECORD;
    candidate_region RECORD;
    common_region_kind SMALLINT;
BEGIN
    SELECT source_interface_id, source_region_id, recency_class
      INTO demand_row
      FROM execution.semantic_pnf_demand
     WHERE demand_id = NEW.demand_id;
    IF demand_row.source_interface_id IS NULL THEN
        RETURN NULL;
    END IF;

    NEW.common_scope_interface_id := execution.nearest_common_pnf_interface(
        demand_row.source_interface_id,
        NEW.source_interface_id
    );
    IF NEW.common_scope_interface_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT region_id, parent_region_id, start_char, end_char, region_kind
      INTO source_region
      FROM execution.semantic_pnf_region
     WHERE region_id = demand_row.source_region_id;
    SELECT region.region_id,
           region.parent_region_id,
           region.start_char,
           region.end_char,
           region.region_kind
      INTO candidate_region
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE interface.interface_id = NEW.source_interface_id;
    SELECT region.region_kind
      INTO common_region_kind
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE interface.interface_id = NEW.common_scope_interface_id;

    IF source_region.region_id IS NULL OR candidate_region.region_id IS NULL THEN
        RETURN NULL;
    END IF;

    CASE demand_row.recency_class
        WHEN 1 THEN
            IF source_region.region_id <> candidate_region.region_id THEN
                RETURN NULL;
            END IF;
        WHEN 2 THEN
            IF source_region.parent_region_id IS DISTINCT FROM
                   candidate_region.parent_region_id
               OR candidate_region.end_char > source_region.start_char THEN
                RETURN NULL;
            END IF;
        WHEN 3 THEN
            IF candidate_region.region_id <> source_region.region_id
               AND candidate_region.end_char > source_region.start_char THEN
                RETURN NULL;
            END IF;
        WHEN 4 THEN
            IF common_region_kind IS NULL OR common_region_kind < 3 THEN
                RETURN NULL;
            END IF;
        WHEN 5 THEN
            IF common_region_kind IS NULL OR common_region_kind > 10 THEN
                RETURN NULL;
            END IF;
        ELSE
            RETURN NULL;
    END CASE;

    NEW.validation_state := 2;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_candidate_visibility
    ON execution.semantic_pnf_demand_candidate;
CREATE TRIGGER semantic_pnf_demand_candidate_visibility
BEFORE INSERT OR UPDATE OF source_interface_id
ON execution.semantic_pnf_demand_candidate
FOR EACH ROW
EXECUTE FUNCTION execution.validate_numeric_pnf_demand_candidate();

COMMIT;
