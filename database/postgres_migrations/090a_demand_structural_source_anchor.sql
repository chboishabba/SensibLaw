BEGIN;

-- 090a: repair the structural source anchor consumed by 091.  A demand may name
-- one exact source object only when its existing source-region + lexical symbol
-- coordinates identify exactly one object.  Ambiguity remains NULL; this column
-- has no identity, resolution, or refutation authority.

ALTER TABLE execution.semantic_pnf_demand
    ADD COLUMN IF NOT EXISTS source_object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_source_object_idx
    ON execution.semantic_pnf_demand(source_object_id,demand_id)
    WHERE source_object_id IS NOT NULL;

CREATE OR REPLACE FUNCTION execution.resolve_numeric_pnf_demand_source_object(
    selected_demand_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_object_id BIGINT;
BEGIN
    SELECT CASE WHEN count(*)=1 THEN min(object.object_id) ELSE NULL END
      INTO resolved_object_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_object AS object
        ON object.region_id=demand.source_region_id
       AND object.active
       AND demand.lexical_symbol_id IS NOT NULL
       AND object.head_symbol_id=demand.lexical_symbol_id
     WHERE demand.demand_id=selected_demand_id;

    UPDATE execution.semantic_pnf_demand
       SET source_object_id=resolved_object_id
     WHERE demand_id=selected_demand_id
       AND source_object_id IS DISTINCT FROM resolved_object_id;
    RETURN resolved_object_id;
END;
$$;

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_demand_source_object_on_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM execution.resolve_numeric_pnf_demand_source_object(NEW.demand_id);
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_source_object_anchor
AFTER INSERT OR UPDATE OF source_region_id,lexical_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW EXECUTE FUNCTION execution.refresh_numeric_pnf_demand_source_object_on_insert();

SELECT execution.resolve_numeric_pnf_demand_source_object(demand_id)
  FROM execution.semantic_pnf_demand;

COMMIT;
