BEGIN;

-- Reference multiplicity is part of the typed demand, not inferred from
-- candidate count alone.  In particular, two compatible actors for a singular
-- anaphor are ambiguous, while two compatible actors for an explicitly plural
-- reference form a plural frontier.  Generic and inapplicable references are
-- likewise explicit semantic modes supplied by the parser/composer.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_reference_mode (
    reference_mode SMALLINT PRIMARY KEY,
    reference_name TEXT NOT NULL UNIQUE
);
INSERT INTO execution.semantic_pnf_reference_mode (reference_mode, reference_name)
VALUES
    (1, 'singular'),
    (2, 'plural'),
    (3, 'generic'),
    (4, 'inapplicable')
ON CONFLICT (reference_mode) DO UPDATE
SET reference_name = EXCLUDED.reference_name;

ALTER TABLE execution.semantic_pnf_demand
    ADD COLUMN IF NOT EXISTS reference_mode SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_pnf_reference_mode(reference_mode)
        ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_reference_mode_idx
    ON execution.semantic_pnf_demand(reference_mode, state, demand_id);

CREATE OR REPLACE FUNCTION execution.classify_numeric_pnf_reference_outcome()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_reference_mode SMALLINT;
BEGIN
    SELECT demand.reference_mode
      INTO selected_reference_mode
      FROM execution.semantic_pnf_demand AS demand
     WHERE demand.demand_id = NEW.demand_id;

    -- Singular preserves the sparse solver's ordinary unique/ambiguous/
    -- no-witness/deferred classification.
    IF selected_reference_mode = 1 OR selected_reference_mode IS NULL THEN
        RETURN NEW;
    END IF;

    IF selected_reference_mode = 2 THEN
        -- A plural reference needs at least one compatible member.  Zero
        -- witnesses remains no-witness/deferred rather than manufacturing a
        -- plural set from nothing.
        IF NEW.candidate_count > 0 THEN
            NEW.outcome_state := 5;
            NEW.selected_target_kind := NULL;
            NEW.selected_target_id := NULL;
        END IF;
    ELSIF selected_reference_mode = 3 THEN
        NEW.outcome_state := 4;
        NEW.selected_target_kind := NULL;
        NEW.selected_target_id := NULL;
    ELSIF selected_reference_mode = 4 THEN
        NEW.outcome_state := 6;
        NEW.selected_target_kind := NULL;
        NEW.selected_target_id := NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_reference_outcome_classification
    ON execution.semantic_pnf_frontier_resolution;
CREATE TRIGGER semantic_pnf_reference_outcome_classification
BEFORE INSERT OR UPDATE OF outcome_state, candidate_count,
    selected_target_kind, selected_target_id
ON execution.semantic_pnf_frontier_resolution
FOR EACH ROW
EXECUTE FUNCTION execution.classify_numeric_pnf_reference_outcome();

-- Non-singular references never carry a scalar resolved target on the demand
-- row.  Keep the current demand carrier aligned with the proof outcome after
-- the frontier row has been classified.
CREATE OR REPLACE FUNCTION execution.align_numeric_pnf_reference_demand_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_reference_mode SMALLINT;
BEGIN
    SELECT demand.reference_mode
      INTO selected_reference_mode
      FROM execution.semantic_pnf_demand AS demand
     WHERE demand.demand_id = NEW.demand_id;

    IF selected_reference_mode IN (2, 3, 4) THEN
        UPDATE execution.semantic_pnf_demand
           SET state = CASE
                   WHEN NEW.outcome_state IN (4, 5, 6) THEN 1
                   ELSE state
               END,
               resolved_target_kind = NULL,
               resolved_target_id = NULL,
               candidate_count = NEW.candidate_count
         WHERE demand_id = NEW.demand_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_reference_demand_state_alignment
    ON execution.semantic_pnf_frontier_resolution;
CREATE TRIGGER semantic_pnf_reference_demand_state_alignment
AFTER INSERT OR UPDATE OF outcome_state, candidate_count,
    selected_target_kind, selected_target_id
ON execution.semantic_pnf_frontier_resolution
FOR EACH ROW
EXECUTE FUNCTION execution.align_numeric_pnf_reference_demand_state();

COMMIT;
