BEGIN;

-- 170: migration 046 decomposed demand/interface batches into row triggers even
-- though both operations are relational projections. Preserve the generic
-- compatibility seam while allowing numeric producers to remain batched.

DROP TRIGGER IF EXISTS semantic_pnf_demand_export
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_interface_demand_binding
    ON execution.semantic_pnf_interface;

CREATE OR REPLACE FUNCTION execution.export_numeric_pnf_inserted_demands_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id,export_kind,target_kind,target_id,
         key_symbol_id,role_symbol_id,residual_type_symbol_id,
         rank,promotion_score)
    SELECT demand.source_interface_id,5,3,demand.demand_id,
           demand.lexical_symbol_id,demand.role_symbol_id,
           demand.residual_type_symbol_id,demand.demand_id,0
      FROM inserted_demand AS demand
     WHERE demand.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id,key_kind,key_a,key_b,target_kind,target_id,rank)
    SELECT demand.source_interface_id,5,demand.residual_type_symbol_id,
           COALESCE(demand.expected_factor_type_symbol_id,0),
           3,demand.demand_id,demand.demand_id
      FROM inserted_demand AS demand
     WHERE demand.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id,key_kind,key_a,key_b,target_kind,target_id,rank)
    SELECT demand.source_interface_id,3,demand.lexical_symbol_id,
           demand.residual_type_symbol_id,3,demand.demand_id,demand.demand_id
      FROM inserted_demand AS demand
     WHERE demand.source_interface_id IS NOT NULL
       AND demand.lexical_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_export_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.export_numeric_pnf_inserted_demands_batch();

CREATE OR REPLACE FUNCTION execution.export_numeric_pnf_updated_demands_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Migration 046 fired on UPDATE OF source_interface_id only. Keep that exact
    -- generic boundary: specialized demand projections own lexical/type changes.
    WITH changed AS MATERIALIZED (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.source_interface_id
                   IS DISTINCT FROM prior.source_interface_id
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id,export_kind,target_kind,target_id,
         key_symbol_id,role_symbol_id,residual_type_symbol_id,
         rank,promotion_score)
    SELECT demand.source_interface_id,5,3,demand.demand_id,
           demand.lexical_symbol_id,demand.role_symbol_id,
           demand.residual_type_symbol_id,demand.demand_id,0
      FROM changed AS demand
     WHERE demand.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    WITH changed AS MATERIALIZED (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.source_interface_id
                   IS DISTINCT FROM prior.source_interface_id
    )
    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id,key_kind,key_a,key_b,target_kind,target_id,rank)
    SELECT demand.source_interface_id,5,demand.residual_type_symbol_id,
           COALESCE(demand.expected_factor_type_symbol_id,0),
           3,demand.demand_id,demand.demand_id
      FROM changed AS demand
     WHERE demand.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    WITH changed AS MATERIALIZED (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.source_interface_id
                   IS DISTINCT FROM prior.source_interface_id
    )
    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id,key_kind,key_a,key_b,target_kind,target_id,rank)
    SELECT demand.source_interface_id,3,demand.lexical_symbol_id,
           demand.residual_type_symbol_id,3,demand.demand_id,demand.demand_id
      FROM changed AS demand
     WHERE demand.source_interface_id IS NOT NULL
       AND demand.lexical_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_export_update_batch
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.export_numeric_pnf_updated_demands_batch();

CREATE OR REPLACE FUNCTION execution.bind_numeric_pnf_inserted_interfaces_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE execution.semantic_pnf_demand AS demand
       SET source_interface_id=interface.interface_id
      FROM inserted_interface AS interface
     WHERE demand.source_region_id=interface.region_id
       AND demand.source_interface_id IS NULL;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_interface_demand_binding_batch
AFTER INSERT ON execution.semantic_pnf_interface
REFERENCING NEW TABLE AS inserted_interface
FOR EACH STATEMENT
EXECUTE FUNCTION execution.bind_numeric_pnf_inserted_interfaces_batch();

COMMIT;
