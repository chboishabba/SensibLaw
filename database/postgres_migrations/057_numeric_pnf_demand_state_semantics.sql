BEGIN;

-- Runtime codebooks define:
--   1 = open
--   2 = resolved
--   3 = deferred_world
--   4 = failed
-- Candidate availability is represented by candidate rows/counts, never by
-- state=2. Repair earlier planner output before enforcing the invariant.
UPDATE execution.semantic_pnf_demand
   SET state = 1
 WHERE state = 2
   AND resolved_target_kind IS NULL
   AND resolved_target_id IS NULL;

ALTER TABLE execution.semantic_pnf_demand
    DROP CONSTRAINT IF EXISTS semantic_pnf_demand_resolution_state_ck;
ALTER TABLE execution.semantic_pnf_demand
    ADD CONSTRAINT semantic_pnf_demand_resolution_state_ck CHECK (
        (
            state = 2
            AND resolved_target_kind IS NOT NULL
            AND resolved_target_id IS NOT NULL
        )
        OR
        (
            state <> 2
            AND resolved_target_kind IS NULL
            AND resolved_target_id IS NULL
        )
    );

CREATE OR REPLACE FUNCTION execution.enforce_numeric_pnf_demand_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Compatibility protection for planner definitions from migrations 049/053:
    -- their candidate-count update attempted state=2. Keep the demand open.
    IF NEW.state = 2
       AND NEW.resolved_target_kind IS NULL
       AND NEW.resolved_target_id IS NULL
       AND NEW.candidate_count > 0 THEN
        NEW.state := 1;
    END IF;

    IF NEW.state = 2
       AND (
           NEW.resolved_target_kind IS NULL
           OR NEW.resolved_target_id IS NULL
       ) THEN
        RAISE EXCEPTION
            'resolved numeric PNF demand % lacks a resolved target',
            NEW.demand_id;
    END IF;
    IF NEW.state <> 2
       AND (
           NEW.resolved_target_kind IS NOT NULL
           OR NEW.resolved_target_id IS NOT NULL
       ) THEN
        RAISE EXCEPTION
            'unresolved numeric PNF demand % carries a resolved target',
            NEW.demand_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_state_semantics
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_state_semantics
BEFORE INSERT OR UPDATE OF
    state,
    candidate_count,
    resolved_target_kind,
    resolved_target_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.enforce_numeric_pnf_demand_state();

COMMIT;
