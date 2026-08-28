BEGIN;

-- Keep the production default conservative while allowing a caller that has
-- explicitly admitted a larger exact-work envelope to carry that admission
-- across the Python/SQL authority boundary.  The setting is transaction-local;
-- callers that do not set it retain the historical 8192 policy.
CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier(
    selected_interface_id BIGINT
)
RETURNS TABLE (
    output_export_count BIGINT,
    unresolved_demand_count BIGINT,
    resolved_demand_count BIGINT,
    actor_profile_count BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region_id BIGINT;
    selected_depth BIGINT := 0;
    selected_key_budget BIGINT := 8192;
    configured_budget TEXT;
BEGIN
    configured_budget := current_setting(
        'sensiblaw.interface_key_budget',
        true
    );
    IF configured_budget IS NOT NULL AND btrim(configured_budget) <> '' THEN
        BEGIN
            selected_key_budget := configured_budget::BIGINT;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION
                'invalid sensiblaw.interface_key_budget: %',
                configured_budget;
        END;
    END IF;
    IF selected_key_budget < 1 THEN
        RAISE EXCEPTION
            'sensiblaw.interface_key_budget must be positive: %',
            selected_key_budget;
    END IF;

    SELECT interface.region_id
      INTO selected_region_id
      FROM execution.semantic_pnf_interface AS interface
     WHERE interface.interface_id = selected_interface_id;

    IF selected_region_id IS NULL THEN
        RAISE EXCEPTION 'numeric PNF interface % disappeared', selected_interface_id;
    END IF;

    WITH RECURSIVE ancestry(region_id, parent_region_id, depth) AS (
        SELECT region.region_id,
               region.parent_region_id,
               0::BIGINT
          FROM execution.semantic_pnf_region AS region
         WHERE region.region_id = selected_region_id
        UNION ALL
        SELECT parent.region_id,
               parent.parent_region_id,
               ancestry.depth + 1
          FROM ancestry
          JOIN execution.semantic_pnf_region AS parent
            ON parent.region_id = ancestry.parent_region_id
         WHERE parent.region_kind <> 9
    )
    SELECT COALESCE(max(depth), 0)
      INTO selected_depth
      FROM ancestry;

    RETURN QUERY
    SELECT receipt.output_export_count,
           receipt.unresolved_demand_count,
           receipt.resolved_demand_count,
           receipt.actor_profile_count
      FROM execution.reduce_numeric_pnf_parent_frontier_delta_native(
          selected_interface_id,
          selected_depth,
          selected_key_budget
      ) AS receipt;
END;
$$;

COMMENT ON FUNCTION execution.rebuild_numeric_pnf_parent_frontier(BIGINT) IS
    'Canonical parent-frontier API. Uses transaction-local sensiblaw.interface_key_budget when explicitly admitted; defaults to 8192 and remains fail-closed.';

COMMIT;
