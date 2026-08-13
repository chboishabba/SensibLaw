BEGIN;

-- 125: source_object_id is now only the unique fast-path projection of the
-- canonical strong occurrence carrier. It is not reconstructed from region +
-- lexical uniqueness. Multiple exact occurrences remain explicit in support.
CREATE OR REPLACE FUNCTION execution.resolve_numeric_pnf_demand_source_object(
    selected_demand_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_object_id BIGINT;
BEGIN
    SELECT CASE WHEN count(DISTINCT support.object_id)=1
                THEN min(support.object_id) ELSE NULL END
      INTO resolved_object_id
      FROM execution.semantic_pnf_demand_occurrence_support support
     WHERE support.demand_id=selected_demand_id
       AND support.support_kind IN (1,2);

    UPDATE execution.semantic_pnf_demand
       SET source_object_id=resolved_object_id
     WHERE demand_id=selected_demand_id
       AND source_object_id IS DISTINCT FROM resolved_object_id;
    RETURN resolved_object_id;
END;
$$;

-- First rebuild strong support from persisted interfaces, then project the
-- unique fast path. The occurrence-support refresh trigger makes the second
-- operation idempotent after source_object_id changes.
SELECT execution.refresh_numeric_pnf_demand_occurrence_support(demand_id)
  FROM execution.semantic_pnf_demand;
SELECT execution.resolve_numeric_pnf_demand_source_object(demand_id)
  FROM execution.semantic_pnf_demand;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_occurrence_projection_audit_v1 AS
SELECT audit.*,
       demand.source_object_id,
       CASE
         WHEN audit.strong_support_count=0 THEN 1
         WHEN count_strong.strong_object_count=1 AND demand.source_object_id IS NOT NULL THEN 2
         WHEN count_strong.strong_object_count>1 AND demand.source_object_id IS NULL THEN 3
         ELSE 4
       END::SMALLINT AS projection_state
  FROM execution.semantic_pnf_demand_occurrence_support_audit_v1 audit
  JOIN execution.semantic_pnf_demand demand USING(demand_id)
  CROSS JOIN LATERAL (
      SELECT count(DISTINCT support.object_id)::BIGINT AS strong_object_count
        FROM execution.semantic_pnf_demand_occurrence_support support
       WHERE support.demand_id=audit.demand_id
         AND support.support_kind IN (1,2)
  ) count_strong;

COMMIT;
