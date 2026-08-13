BEGIN;

CREATE OR REPLACE FUNCTION execution.plan_demands_after_visible_lookup_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
BEGIN
    FOR selected IN
        SELECT DISTINCT region.run_ref, region.document_ref
          FROM inserted_visible
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.interface_id = inserted_visible.interface_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
    LOOP
        PERFORM execution.plan_numeric_pnf_demand_candidates(
            selected.run_ref,
            selected.document_ref
        );
    END LOOP;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_visible_demand_planning
    ON execution.semantic_pnf_visible_lookup;
CREATE TRIGGER semantic_pnf_visible_demand_planning
AFTER INSERT ON execution.semantic_pnf_visible_lookup
REFERENCING NEW TABLE AS inserted_visible
FOR EACH STATEMENT
EXECUTE FUNCTION execution.plan_demands_after_visible_lookup_refresh();

COMMIT;
