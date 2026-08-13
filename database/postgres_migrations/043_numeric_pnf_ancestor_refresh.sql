BEGIN;

CREATE OR REPLACE FUNCTION execution.rebuild_pnf_document_ancestors(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    row RECORD;
    rebuilt_count BIGINT := 0;
BEGIN
    DELETE FROM execution.semantic_pnf_interface_ancestor AS ancestor
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
    WHERE ancestor.interface_id = interface.interface_id
      AND interface.region_id = region.region_id
      AND region.run_ref = selected_run_ref
      AND region.document_ref = selected_document_ref;

    DELETE FROM execution.semantic_pnf_interface_typed_ancestor AS ancestor
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
    WHERE ancestor.interface_id = interface.interface_id
      AND interface.region_id = region.region_id
      AND region.run_ref = selected_run_ref
      AND region.document_ref = selected_document_ref;

    FOR row IN
        WITH RECURSIVE hierarchy(interface_id, depth) AS (
            SELECT interface.interface_id, 0
              FROM execution.semantic_pnf_interface AS interface
              JOIN execution.semantic_pnf_region AS region
                ON region.region_id = interface.region_id
             WHERE region.run_ref = selected_run_ref
               AND region.document_ref = selected_document_ref
               AND interface.parent_interface_id IS NULL
            UNION ALL
            SELECT child.interface_id, hierarchy.depth + 1
              FROM hierarchy
              JOIN execution.semantic_pnf_interface AS child
                ON child.parent_interface_id = hierarchy.interface_id
        )
        SELECT interface_id
          FROM hierarchy
         ORDER BY depth, interface_id
    LOOP
        PERFORM execution.rebuild_pnf_interface_ancestors(row.interface_id);
        rebuilt_count := rebuilt_count + 1;
    END LOOP;
    RETURN rebuilt_count;
END;
$$;

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_ancestors_on_document_close()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.region_kind = 10
       AND NEW.closure_state = 3
       AND OLD.closure_state IS DISTINCT FROM NEW.closure_state THEN
        PERFORM execution.rebuild_pnf_document_ancestors(
            NEW.run_ref,
            NEW.document_ref
        );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_document_ancestor_refresh
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_document_ancestor_refresh
AFTER UPDATE OF closure_state
ON execution.semantic_pnf_region
FOR EACH ROW
EXECUTE FUNCTION execution.refresh_numeric_pnf_ancestors_on_document_close();

COMMIT;
