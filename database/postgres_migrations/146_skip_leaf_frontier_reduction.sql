BEGIN;

-- 146: a canonical leaf is not a canonical parent frontier.
--
-- Sentence admission materializes the sentence interface directly, including
-- exports, lookup rows, unresolved demands and the exact interface digest.
-- Migration 062's parent reducer has a region_kind=1 special case that merely
-- recounts those already-materialized exports/demands and returns. Migration
-- 145 then attempts to enqueue parent_interface_id, which is normally absent
-- until paragraph interfaces are materialized later.
--
-- Running that parent-reducer path once per sentence therefore has no semantic
-- effect but introduces fixed query work proportional to sentence count. The
-- hierarchy planner later closes paragraph/adaptive/document parent frontiers
-- from the sentence exports themselves. Exclude sentence leaves from the
-- parent-frontier trigger just as the sparse document recovery path already
-- excludes them.

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

    -- 1 = sentence leaf: its own producer has already materialized its exact
    -- interface. 2/4/9 are overlapping/evidence fibres. None is a canonical
    -- parent frontier and none may invoke the parent reducer here.
    IF NEW.region_kind IN (1, 2, 4, 9) THEN
        RETURN NEW;
    END IF;

    SELECT interface_id
      INTO selected_interface_id
      FROM execution.semantic_pnf_interface
     WHERE region_id = NEW.region_id;

    IF selected_interface_id IS NULL THEN
        RETURN NEW;
    END IF;

    PERFORM *
      FROM execution.rebuild_numeric_pnf_parent_frontier(
          selected_interface_id
      );
    RETURN NEW;
END;
$$;

COMMIT;
