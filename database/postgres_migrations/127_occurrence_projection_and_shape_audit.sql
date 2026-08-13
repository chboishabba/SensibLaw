BEGIN;

-- 127: keep the unique strong occurrence projection separate from the historical
-- source_object_id column. The latter keeps 090a semantics and its kind-9 audit
-- receipts; the former is a rebuildable fast path over strong occurrence support.

ALTER TABLE execution.semantic_pnf_demand
    ADD COLUMN IF NOT EXISTS occurrence_source_object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_occurrence_source_object_idx
    ON execution.semantic_pnf_demand(occurrence_source_object_id,demand_id)
    WHERE occurrence_source_object_id IS NOT NULL;

CREATE OR REPLACE FUNCTION execution.resolve_numeric_pnf_demand_occurrence_source_object(
    selected_demand_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_object_id BIGINT;
BEGIN
    SELECT CASE WHEN count(DISTINCT support.object_id)=1
                THEN min(support.object_id) ELSE NULL END
      INTO resolved_object_id
      FROM execution.semantic_pnf_demand_occurrence_support AS support
     WHERE support.demand_id=selected_demand_id
       AND support.support_kind IN (1,2);

    UPDATE execution.semantic_pnf_demand
       SET occurrence_source_object_id=resolved_object_id
     WHERE demand_id=selected_demand_id
       AND occurrence_source_object_id IS DISTINCT FROM resolved_object_id;
    RETURN resolved_object_id;
END;
$$;

SELECT execution.resolve_numeric_pnf_demand_occurrence_source_object(demand_id)
  FROM execution.semantic_pnf_demand;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_occurrence_projection_audit_v1 AS
SELECT audit.*,
       demand.source_object_id AS legacy_source_object_id,
       demand.occurrence_source_object_id,
       strong_count.strong_object_count,
       CASE
         WHEN audit.strong_support_count=0 THEN 1
         WHEN strong_count.strong_object_count=1
              AND demand.occurrence_source_object_id IS NOT NULL THEN 2
         WHEN strong_count.strong_object_count>1
              AND demand.occurrence_source_object_id IS NULL THEN 3
         ELSE 4
       END::SMALLINT AS projection_state
  FROM execution.semantic_pnf_demand_occurrence_support_audit_v1 AS audit
  JOIN execution.semantic_pnf_demand AS demand USING(demand_id)
  CROSS JOIN LATERAL (
      SELECT count(DISTINCT support.object_id)::BIGINT AS strong_object_count
        FROM execution.semantic_pnf_demand_occurrence_support AS support
       WHERE support.demand_id=audit.demand_id
         AND support.support_kind IN (1,2)
  ) AS strong_count;

-- Record the coordinate family each producer left behind. This is an
-- observability surface only; it does not infer missing coordinates.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_coordinate_shape_v1 AS
SELECT demand.demand_id,
       (demand.source_interface_id IS NOT NULL) AS has_interface,
       (demand.lexical_symbol_id IS NOT NULL) AS has_lexical,
       (demand.role_symbol_id IS NOT NULL) AS has_role,
       (demand.expected_factor_type_symbol_id IS NOT NULL) AS has_factor_type,
       (demand.expected_object_kind_symbol_id IS NOT NULL) AS has_object_kind,
       CASE
         WHEN demand.lexical_symbol_id IS NOT NULL
              AND demand.role_symbol_id IS NOT NULL THEN 1
         WHEN demand.lexical_symbol_id IS NOT NULL THEN 2
         WHEN demand.role_symbol_id IS NOT NULL THEN 3
         ELSE 4
       END::SMALLINT AS coordinate_shape
  FROM execution.semantic_pnf_demand AS demand;

COMMIT;
