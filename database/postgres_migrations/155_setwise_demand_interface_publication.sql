BEGIN;

-- 155: migration 046's semantic_pnf_demand_export row trigger decomposed one
-- set-wise source_interface_id binding UPDATE into one PL/pgSQL invocation and
-- up to three INSERT statements per demand. Strict sentence admission binds all
-- of a sentence's demands in one UPDATE when its interface is created. Preserve
-- that finite demand fibre through the physical boundary with transition-table
-- projections.
--
-- The original export_numeric_pnf_demand() function remains available as a
-- one-demand compatibility/repair API; ordinary INSERT/UPDATE publication no
-- longer calls it row-by-row.

DROP TRIGGER IF EXISTS semantic_pnf_demand_export
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.publish_inserted_numeric_pnf_demands()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score)
    SELECT demand.source_interface_id,
           5,
           3,
           demand.demand_id,
           demand.lexical_symbol_id,
           demand.role_symbol_id,
           demand.residual_type_symbol_id,
           demand.demand_id,
           0
      FROM inserted_demand AS demand
     WHERE demand.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT demand.source_interface_id,
           5,
           demand.residual_type_symbol_id,
           COALESCE(demand.expected_factor_type_symbol_id, 0),
           3,
           demand.demand_id,
           demand.demand_id
      FROM inserted_demand AS demand
     WHERE demand.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT demand.source_interface_id,
           3,
           demand.lexical_symbol_id,
           demand.residual_type_symbol_id,
           3,
           demand.demand_id,
           demand.demand_id
      FROM inserted_demand AS demand
     WHERE demand.source_interface_id IS NOT NULL
       AND demand.lexical_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_export_insert_setwise
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.publish_inserted_numeric_pnf_demands();

CREATE OR REPLACE FUNCTION execution.publish_rebound_numeric_pnf_demands()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score)
    SELECT demand.source_interface_id,
           5,
           3,
           demand.demand_id,
           demand.lexical_symbol_id,
           demand.role_symbol_id,
           demand.residual_type_symbol_id,
           demand.demand_id,
           0
      FROM rebound_demand AS demand
      JOIN prior_demand AS prior USING (demand_id)
     WHERE demand.source_interface_id IS NOT NULL
       AND demand.source_interface_id IS DISTINCT FROM prior.source_interface_id
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT demand.source_interface_id,
           5,
           demand.residual_type_symbol_id,
           COALESCE(demand.expected_factor_type_symbol_id, 0),
           3,
           demand.demand_id,
           demand.demand_id
      FROM rebound_demand AS demand
      JOIN prior_demand AS prior USING (demand_id)
     WHERE demand.source_interface_id IS NOT NULL
       AND demand.source_interface_id IS DISTINCT FROM prior.source_interface_id
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT demand.source_interface_id,
           3,
           demand.lexical_symbol_id,
           demand.residual_type_symbol_id,
           3,
           demand.demand_id,
           demand.demand_id
      FROM rebound_demand AS demand
      JOIN prior_demand AS prior USING (demand_id)
     WHERE demand.source_interface_id IS NOT NULL
       AND demand.source_interface_id IS DISTINCT FROM prior.source_interface_id
       AND demand.lexical_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_export_update_setwise
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS rebound_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.publish_rebound_numeric_pnf_demands();

COMMIT;
