BEGIN;

-- 156: migration 122 maintained exact occurrence support one demand/export row
-- at a time. Sentence interface binding is already one set-wise UPDATE and
-- sentence export publication is already one set-wise INSERT, so the row hooks
-- amplified those finite fibres into repeated delete/rebuild cycles.
--
-- Keep the existing one-demand refresh function as an explicit repair API. The
-- hot triggers now collect affected demand ids and rebuild the same support
-- carrier in three relational projections over that bounded id set.

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_demand_occurrence_support(
    selected_demand_ids BIGINT[]
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected BIGINT := 0;
    n BIGINT := 0;
BEGIN
    IF selected_demand_ids IS NULL
       OR cardinality(selected_demand_ids) = 0 THEN
        RETURN 0;
    END IF;

    DELETE FROM execution.semantic_pnf_demand_occurrence_support
     WHERE demand_id = ANY(selected_demand_ids);

    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,
         role_symbol_id,lexical_symbol_id)
    SELECT DISTINCT demand.demand_id,
           1::SMALLINT,
           demand.source_interface_id,
           export.target_id,
           demand.role_symbol_id,
           demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id = demand.source_interface_id
       AND export.target_kind = 1
       AND export.export_kind = 1
       AND demand.lexical_symbol_id IS NOT NULL
       AND export.key_symbol_id = demand.lexical_symbol_id
       AND demand.role_symbol_id IS NOT NULL
       AND export.role_symbol_id = demand.role_symbol_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = export.target_id
       AND object.active
     WHERE demand.demand_id = ANY(selected_demand_ids)
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT;
    affected := affected + n;

    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,factor_id,
         slot_ordinal,role_symbol_id,lexical_symbol_id)
    SELECT DISTINCT demand.demand_id,
           2::SMALLINT,
           demand.source_interface_id,
           edge.object_id,
           factor.factor_id,
           edge.slot_ordinal,
           edge.role_symbol_id,
           demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id = demand.source_interface_id
       AND export.target_kind = 2
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = export.target_id
       AND demand.expected_factor_type_symbol_id IS NOT NULL
       AND factor.factor_type_symbol_id = demand.expected_factor_type_symbol_id
      JOIN execution.semantic_pnf_hyperedge AS edge
        ON edge.factor_id = factor.factor_id
       AND demand.role_symbol_id IS NOT NULL
       AND edge.role_symbol_id = demand.role_symbol_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = edge.object_id
       AND object.active
     WHERE demand.demand_id = ANY(selected_demand_ids)
       AND (
           demand.lexical_symbol_id IS NULL
           OR object.head_symbol_id = demand.lexical_symbol_id
       )
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT;
    affected := affected + n;

    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,
         role_symbol_id,lexical_symbol_id)
    SELECT demand.demand_id,
           9::SMALLINT,
           demand.source_interface_id,
           demand.source_object_id,
           demand.role_symbol_id,
           demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
     WHERE demand.demand_id = ANY(selected_demand_ids)
       AND demand.source_object_id IS NOT NULL
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT;
    affected := affected + n;

    RETURN affected;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_support_refresh
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_export_occurrence_support_refresh
    ON execution.semantic_pnf_interface_export;

CREATE OR REPLACE FUNCTION execution.project_inserted_numeric_pnf_demand_support()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    SELECT array_agg(demand_id ORDER BY demand_id)
      INTO selected_ids
      FROM inserted_demand;
    PERFORM execution.project_numeric_pnf_demand_occurrence_support(selected_ids);
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_occurrence_support_insert_setwise
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_inserted_numeric_pnf_demand_support();

CREATE OR REPLACE FUNCTION execution.project_updated_numeric_pnf_demand_support()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    SELECT array_agg(current.demand_id ORDER BY current.demand_id)
      INTO selected_ids
      FROM updated_demand AS current
      JOIN prior_demand AS prior USING (demand_id)
     WHERE current.source_interface_id
               IS DISTINCT FROM prior.source_interface_id
        OR current.expected_factor_type_symbol_id
               IS DISTINCT FROM prior.expected_factor_type_symbol_id
        OR current.lexical_symbol_id
               IS DISTINCT FROM prior.lexical_symbol_id
        OR current.role_symbol_id
               IS DISTINCT FROM prior.role_symbol_id
        OR current.source_object_id
               IS DISTINCT FROM prior.source_object_id;
    PERFORM execution.project_numeric_pnf_demand_occurrence_support(selected_ids);
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_occurrence_support_update_setwise
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_updated_numeric_pnf_demand_support();

CREATE OR REPLACE FUNCTION execution.project_inserted_export_occurrence_support()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    SELECT array_agg(DISTINCT demand.demand_id ORDER BY demand.demand_id)
      INTO selected_ids
      FROM inserted_export AS export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.source_interface_id = export.interface_id
     WHERE (
         export.target_kind = 1
         AND export.export_kind = 1
         AND demand.lexical_symbol_id IS NOT NULL
         AND export.key_symbol_id = demand.lexical_symbol_id
         AND demand.role_symbol_id IS NOT NULL
         AND export.role_symbol_id = demand.role_symbol_id
     ) OR export.target_kind = 2;
    PERFORM execution.project_numeric_pnf_demand_occurrence_support(selected_ids);
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_export_occurrence_support_insert_setwise
AFTER INSERT ON execution.semantic_pnf_interface_export
REFERENCING NEW TABLE AS inserted_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_inserted_export_occurrence_support();

CREATE OR REPLACE FUNCTION execution.project_updated_export_occurrence_support()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    WITH affected_interface AS (
        SELECT interface_id FROM prior_export
        UNION
        SELECT interface_id FROM updated_export
    )
    SELECT array_agg(DISTINCT demand.demand_id ORDER BY demand.demand_id)
      INTO selected_ids
      FROM affected_interface AS affected
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.source_interface_id = affected.interface_id;
    PERFORM execution.project_numeric_pnf_demand_occurrence_support(selected_ids);
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_export_occurrence_support_update_setwise
AFTER UPDATE ON execution.semantic_pnf_interface_export
REFERENCING OLD TABLE AS prior_export NEW TABLE AS updated_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_updated_export_occurrence_support();

COMMIT;
