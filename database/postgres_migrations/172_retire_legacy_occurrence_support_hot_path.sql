BEGIN;

-- 172: migration 122's generic demand occurrence-support carrier is no longer
-- H9 authority after migration 135 moved world/proof work to producer-authored
-- trigger/target/evidence occurrence provenance. Keep 122 for audit and
-- compatibility, but stop paying for its per-demand and per-export automatic
-- refresh loops during ordinary production.

DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_support_refresh
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_export_occurrence_support_refresh
    ON execution.semantic_pnf_interface_export;

COMMENT ON FUNCTION execution.refresh_numeric_pnf_demand_occurrence_support(BIGINT) IS
'Cold compatibility/audit rebuild for one demand. Automatic production maintenance retired by migration 172; current H9 authority is producer-authored occurrence provenance from migration 135/171.';

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_demand_occurrence_support_scope(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected BIGINT := 0;
    n BIGINT := 0;
BEGIN
    DELETE FROM execution.semantic_pnf_demand_occurrence_support AS support
    USING execution.semantic_pnf_demand AS demand,
          execution.semantic_pnf_region AS region
    WHERE support.demand_id=demand.demand_id
      AND region.region_id=demand.source_region_id
      AND region.run_id=selected_run_id
      AND region.document_id=selected_document_id;

    -- Exact object occurrence exported on the same interface under the same
    -- lexical key and grammatical role. Preserve every exact match.
    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,
         role_symbol_id,lexical_symbol_id)
    SELECT DISTINCT demand.demand_id,1::SMALLINT,demand.source_interface_id,
           export.target_id,demand.role_symbol_id,demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id=demand.source_interface_id
       AND export.target_kind=1
       AND export.export_kind=1
       AND demand.lexical_symbol_id IS NOT NULL
       AND export.key_symbol_id=demand.lexical_symbol_id
       AND demand.role_symbol_id IS NOT NULL
       AND export.role_symbol_id=demand.role_symbol_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id=export.target_id
       AND object.active
     WHERE region.run_id=selected_run_id
       AND region.document_id=selected_document_id
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT;
    affected:=affected+n;

    -- Exact typed factor-slot origin.
    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,factor_id,
         slot_ordinal,role_symbol_id,lexical_symbol_id)
    SELECT DISTINCT demand.demand_id,2::SMALLINT,demand.source_interface_id,
           edge.object_id,factor.factor_id,edge.slot_ordinal,
           edge.role_symbol_id,demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id=demand.source_interface_id
       AND export.target_kind=2
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id=export.target_id
       AND demand.expected_factor_type_symbol_id IS NOT NULL
       AND factor.factor_type_symbol_id=demand.expected_factor_type_symbol_id
      JOIN execution.semantic_pnf_hyperedge AS edge
        ON edge.factor_id=factor.factor_id
       AND demand.role_symbol_id IS NOT NULL
       AND edge.role_symbol_id=demand.role_symbol_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id=edge.object_id
       AND object.active
     WHERE region.run_id=selected_run_id
       AND region.document_id=selected_document_id
       AND (
           demand.lexical_symbol_id IS NULL
           OR object.head_symbol_id=demand.lexical_symbol_id
       )
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT;
    affected:=affected+n;

    -- Historical weak source-object projection retained for comparison only.
    INSERT INTO execution.semantic_pnf_demand_occurrence_support
        (demand_id,support_kind,source_interface_id,object_id,
         role_symbol_id,lexical_symbol_id)
    SELECT demand.demand_id,9::SMALLINT,demand.source_interface_id,
           demand.source_object_id,demand.role_symbol_id,demand.lexical_symbol_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE region.run_id=selected_run_id
       AND region.document_id=selected_document_id
       AND demand.source_object_id IS NOT NULL
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT;
    affected:=affected+n;

    RETURN affected;
END;
$$;

COMMENT ON FUNCTION execution.refresh_numeric_pnf_demand_occurrence_support_scope(BIGINT,BIGINT) IS
'Set-wise cold rebuild of migration-122 occurrence support for one run/document. Not invoked by strict production; use for audit/compatibility reports that explicitly require the legacy carrier.';

COMMIT;
