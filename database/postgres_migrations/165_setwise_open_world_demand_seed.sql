BEGIN;

-- 165: every represented demand begins open-world unless an explicit coverage
-- witness later closes that possibility. Migration 086 seeded this state with
-- one row trigger per demand. The epistemic rule is unchanged; seed the whole
-- inserted demand relation at once.

DROP TRIGGER IF EXISTS semantic_pnf_demand_open_world_seed
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.seed_numeric_pnf_open_world_state_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_open_world_state(demand_id)
    SELECT demand_id
      FROM inserted_demand
    ON CONFLICT(demand_id) DO NOTHING;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_open_world_seed_batch
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.seed_numeric_pnf_open_world_state_batch();

COMMIT;
