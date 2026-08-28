BEGIN;

-- Keep the long-standing canonical SQL API stable while changing its execution
-- owner.  All current Python hierarchy paths and the migration-197 affected
-- document coordinator already call rebuild_numeric_pnf_parent_frontier(); this
-- wrapper routes those calls through the C3b transported-boundary bridge.
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
BEGIN
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
          8192
      ) AS receipt;
END;
$$;

COMMENT ON FUNCTION execution.rebuild_numeric_pnf_parent_frontier(BIGINT) IS
    'Canonical parent-frontier API. Since migration 203, delegates to the C3b delta-native transported-boundary reducer; the historical child-join rebuild survives only in pre-203 migrations and external parity fixtures.';

COMMIT;
