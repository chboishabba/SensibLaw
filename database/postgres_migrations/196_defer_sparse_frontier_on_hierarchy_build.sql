BEGIN;

-- Parent frontier reduction is the canonical reductive boundary operation, but
-- hierarchy materialization already establishes an explicit deferred-publication
-- transaction with sensiblaw.defer_frontier_rebuild=on.  Running the sparse
-- reducer from every region-close trigger inside that transaction duplicates the
-- explicit document frontier phases in numeric_hierarchy_planner.py.
--
-- Preserve ordinary trigger behaviour outside that boundary.  Inside the
-- hierarchy transaction, construction publishes parent interfaces first and the
-- explicit document reducer performs the canonical bottom-up frontier pass.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_interface_on_close()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_interface_id BIGINT;
BEGIN
    IF NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;

    IF COALESCE(
        current_setting('sensiblaw.defer_frontier_rebuild', true),
        'off'
    ) = 'on' THEN
        RETURN NEW;
    END IF;

    SELECT interface_id
      INTO selected_interface_id
      FROM execution.semantic_pnf_interface
     WHERE region_id = NEW.region_id;

    IF selected_interface_id IS NOT NULL THEN
        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected_interface_id
          );
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION execution.reduce_numeric_pnf_interface_on_close() IS
    'Sparse frontier close trigger; honors the hierarchy deferred-publication boundary so parent interfaces are not reduced both eagerly and again by the explicit document frontier phase.';

COMMIT;
