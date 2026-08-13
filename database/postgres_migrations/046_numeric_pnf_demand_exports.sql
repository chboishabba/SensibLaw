BEGIN;

CREATE OR REPLACE FUNCTION execution.export_numeric_pnf_demand()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_interface_id IS NULL THEN
        RETURN NEW;
    END IF;

    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score)
    VALUES (
        NEW.source_interface_id,
        5,
        3,
        NEW.demand_id,
        NEW.lexical_symbol_id,
        NEW.role_symbol_id,
        NEW.residual_type_symbol_id,
        NEW.demand_id,
        0
    )
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    VALUES (
        NEW.source_interface_id,
        5,
        NEW.residual_type_symbol_id,
        COALESCE(NEW.expected_factor_type_symbol_id, 0),
        3,
        NEW.demand_id,
        NEW.demand_id
    )
    ON CONFLICT DO NOTHING;

    IF NEW.lexical_symbol_id IS NOT NULL THEN
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, rank)
        VALUES (
            NEW.source_interface_id,
            3,
            NEW.lexical_symbol_id,
            NEW.residual_type_symbol_id,
            3,
            NEW.demand_id,
            NEW.demand_id
        )
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_export
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_export
AFTER INSERT OR UPDATE OF source_interface_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.export_numeric_pnf_demand();

CREATE OR REPLACE FUNCTION execution.bind_numeric_pnf_region_demands()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE execution.semantic_pnf_demand
       SET source_interface_id = NEW.interface_id
     WHERE source_region_id = NEW.region_id
       AND source_interface_id IS NULL;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_interface_demand_binding
    ON execution.semantic_pnf_interface;
CREATE TRIGGER semantic_pnf_interface_demand_binding
AFTER INSERT ON execution.semantic_pnf_interface
FOR EACH ROW
EXECUTE FUNCTION execution.bind_numeric_pnf_region_demands();

COMMIT;
