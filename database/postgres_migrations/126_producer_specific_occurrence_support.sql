BEGIN;

-- 126: live GWB validation showed that demand provenance is producer-shaped.
-- Most demands carry lexical coordinates OR grammatical-role coordinates, not
-- both. Requiring one universal (interface, lexical, role) tuple was therefore
-- structurally impossible for the corpus.
--
-- kind 1 = lexical-origin object support on the same interface.
-- kind 2 = role/factor-origin support on the same interface.
-- kind 9 = historical 090a source_object_id, audit only.

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_demand_occurrence_support(
    selected_demand_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0; n BIGINT := 0;
BEGIN
    -- Rebuild strong support only. Never delete the historical audit witness.
    DELETE FROM execution.semantic_pnf_demand_occurrence_support
     WHERE demand_id=selected_demand_id
       AND support_kind IN (1,2);

    -- Lexical producer: interface + lexical key are authoritative coordinates.
    -- Role narrows only when that producer actually retained one.
    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,
         role_symbol_id,lexical_symbol_id)
    SELECT DISTINCT demand.demand_id,1::SMALLINT,demand.source_interface_id,
           export.target_id,demand.role_symbol_id,demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id=demand.source_interface_id
       AND export.target_kind=1
       AND export.export_kind=1
       AND export.key_symbol_id=demand.lexical_symbol_id
       AND (demand.role_symbol_id IS NULL
            OR export.role_symbol_id=demand.role_symbol_id)
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id=export.target_id AND object.active
     WHERE demand.demand_id=selected_demand_id
       AND demand.source_interface_id IS NOT NULL
       AND demand.lexical_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    -- Role/factor producer: role is authoritative. Factor/object/lexical
    -- coordinates narrow the structural fibre only when present.
    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,factor_id,
         slot_ordinal,role_symbol_id,lexical_symbol_id)
    SELECT DISTINCT demand.demand_id,2::SMALLINT,demand.source_interface_id,
           edge.object_id,factor.factor_id,edge.slot_ordinal,
           edge.role_symbol_id,demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id=demand.source_interface_id
       AND export.target_kind=2
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id=export.target_id
       AND (demand.expected_factor_type_symbol_id IS NULL
            OR factor.factor_type_symbol_id=demand.expected_factor_type_symbol_id)
      JOIN execution.semantic_pnf_hyperedge AS edge
        ON edge.factor_id=factor.factor_id
       AND edge.role_symbol_id=demand.role_symbol_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id=edge.object_id
       AND object.active
       AND (demand.expected_object_kind_symbol_id IS NULL
            OR object.object_kind_symbol_id=demand.expected_object_kind_symbol_id)
       AND (demand.lexical_symbol_id IS NULL
            OR object.head_symbol_id=demand.lexical_symbol_id)
     WHERE demand.demand_id=selected_demand_id
       AND demand.source_interface_id IS NOT NULL
       AND demand.role_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    -- Preserve/restore the legacy audit witness independently of strong support.
    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,
         role_symbol_id,lexical_symbol_id)
    SELECT demand.demand_id,9::SMALLINT,demand.source_interface_id,
           demand.source_object_id,demand.role_symbol_id,demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
     WHERE demand.demand_id=selected_demand_id
       AND demand.source_object_id IS NOT NULL
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    RETURN affected;
END;
$$;

-- source_object_id is legacy state. Do not cause a strong-support rebuild merely
-- because that historical projection changes.
DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_support_refresh
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_occurrence_support_refresh
AFTER INSERT OR UPDATE OF source_interface_id,expected_factor_type_symbol_id,
    expected_object_kind_symbol_id,lexical_symbol_id,role_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW EXECUTE FUNCTION execution.refresh_numeric_pnf_demand_occurrence_support_on_change();

-- Restore 090a semantics after migration 125 temporarily overloaded this API.
CREATE OR REPLACE FUNCTION execution.resolve_numeric_pnf_demand_source_object(
    selected_demand_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_object_id BIGINT;
BEGIN
    SELECT CASE WHEN count(*)=1 THEN min(object.object_id) ELSE NULL END
      INTO resolved_object_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_object AS object
        ON object.region_id=demand.source_region_id
       AND object.active
       AND demand.lexical_symbol_id IS NOT NULL
       AND object.head_symbol_id=demand.lexical_symbol_id
     WHERE demand.demand_id=selected_demand_id;
    UPDATE execution.semantic_pnf_demand
       SET source_object_id=resolved_object_id
     WHERE demand_id=selected_demand_id
       AND source_object_id IS DISTINCT FROM resolved_object_id;
    RETURN resolved_object_id;
END;
$$;

-- Rebuild without erasing kind 9.
SELECT execution.refresh_numeric_pnf_demand_occurrence_support(demand_id)
  FROM execution.semantic_pnf_demand;

COMMIT;
