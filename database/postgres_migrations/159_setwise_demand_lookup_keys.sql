BEGIN;

-- 159: demand lookup keys are a pure finite projection of demand coordinates.
-- Migration 053 maintained them with one row trigger per demand, including a
-- DELETE + INSERT sequence on updates. Adjacent reconciliation (056) consumes
-- this carrier directly, so it remains live; only its physical maintenance is
-- changed here.

DROP TRIGGER IF EXISTS semantic_pnf_demand_lookup_keys
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_demand_lookup_keys_inserted()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_lookup_key
        (demand_id,key_kind,key_a,key_b,target_kind)
    SELECT demand.demand_id,key_row.key_kind,key_row.key_a,0,demand.expected_target_kind
      FROM inserted_demand AS demand
      CROSS JOIN LATERAL (
          SELECT 1::SMALLINT AS key_kind,demand.expected_factor_type_symbol_id AS key_a
           WHERE demand.expected_factor_type_symbol_id IS NOT NULL
          UNION ALL
          SELECT 2::SMALLINT,demand.expected_object_kind_symbol_id
           WHERE demand.expected_object_kind_symbol_id IS NOT NULL
          UNION ALL
          SELECT 3::SMALLINT,demand.lexical_symbol_id
           WHERE demand.lexical_symbol_id IS NOT NULL
          UNION ALL
          SELECT 5::SMALLINT,demand.residual_type_symbol_id
           WHERE demand.residual_type_symbol_id IS NOT NULL
      ) AS key_row
    ON CONFLICT DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_lookup_keys_insert
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_lookup_keys_insert
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_demand_lookup_keys_inserted();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_demand_lookup_keys_updated()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS MATERIALIZED (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.expected_target_kind IS DISTINCT FROM prior.expected_target_kind
            OR current.expected_factor_type_symbol_id IS DISTINCT FROM prior.expected_factor_type_symbol_id
            OR current.expected_object_kind_symbol_id IS DISTINCT FROM prior.expected_object_kind_symbol_id
            OR current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
            OR current.residual_type_symbol_id IS DISTINCT FROM prior.residual_type_symbol_id
    )
    DELETE FROM execution.semantic_pnf_demand_lookup_key AS key
    USING changed
     WHERE key.demand_id=changed.demand_id;

    WITH changed AS MATERIALIZED (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.expected_target_kind IS DISTINCT FROM prior.expected_target_kind
            OR current.expected_factor_type_symbol_id IS DISTINCT FROM prior.expected_factor_type_symbol_id
            OR current.expected_object_kind_symbol_id IS DISTINCT FROM prior.expected_object_kind_symbol_id
            OR current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
            OR current.residual_type_symbol_id IS DISTINCT FROM prior.residual_type_symbol_id
    )
    INSERT INTO execution.semantic_pnf_demand_lookup_key
        (demand_id,key_kind,key_a,key_b,target_kind)
    SELECT demand.demand_id,key_row.key_kind,key_row.key_a,0,demand.expected_target_kind
      FROM changed AS demand
      CROSS JOIN LATERAL (
          SELECT 1::SMALLINT AS key_kind,demand.expected_factor_type_symbol_id AS key_a
           WHERE demand.expected_factor_type_symbol_id IS NOT NULL
          UNION ALL
          SELECT 2::SMALLINT,demand.expected_object_kind_symbol_id
           WHERE demand.expected_object_kind_symbol_id IS NOT NULL
          UNION ALL
          SELECT 3::SMALLINT,demand.lexical_symbol_id
           WHERE demand.lexical_symbol_id IS NOT NULL
          UNION ALL
          SELECT 5::SMALLINT,demand.residual_type_symbol_id
           WHERE demand.residual_type_symbol_id IS NOT NULL
      ) AS key_row
    ON CONFLICT DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_lookup_keys_update
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_lookup_keys_update
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_demand_lookup_keys_updated();

COMMIT;
