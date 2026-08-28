BEGIN;

-- C3e/systemic hierarchy orchestration ---------------------------------------
--
-- The hierarchy planner already declares sensiblaw.defer_frontier_rebuild while
-- constructing paragraph/adaptive/document topology. Historically the parent
-- rebuild API ignored that declaration, so every shell synchronously published
-- its frontier and the planner then called the document scheduler again at the
-- intended publication barriers.
--
-- Make the defer contract real without copying or replacing the current
-- receipt-driven/affected-only scheduler implementation. We rename the active
-- scheduler object in place and put a force/defer wrapper under its stable API
-- name. This preserves the exact scheduler installed by migrations 197--210.

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
    defer_requested BOOLEAN := FALSE;
    force_requested BOOLEAN := FALSE;
BEGIN
    defer_requested := lower(COALESCE(
        current_setting('sensiblaw.defer_frontier_rebuild', true),
        'off'
    )) IN ('1', 'on', 'true', 'yes');
    force_requested := lower(COALESCE(
        current_setting('sensiblaw.force_frontier_rebuild', true),
        'off'
    )) IN ('1', 'on', 'true', 'yes');

    -- Topology construction may ask for the historical return shape, but no
    -- parent semantic state may publish before an explicit document barrier.
    IF defer_requested AND NOT force_requested THEN
        RETURN QUERY
        SELECT COALESCE(interface.interface_cardinality, 0)::BIGINT,
               COALESCE(interface.unresolved_count, 0)::BIGINT,
               COALESCE((
                   SELECT count(*)
                     FROM execution.semantic_pnf_frontier_resolution AS resolution
                    WHERE resolution.interface_id = selected_interface_id
                      AND resolution.outcome_state = 2
               ), 0)::BIGINT,
               COALESCE((
                   SELECT count(*)
                     FROM execution.semantic_pnf_actor_profile AS profile
                    WHERE profile.interface_id = selected_interface_id
               ), 0)::BIGINT
          FROM execution.semantic_pnf_interface AS interface
         WHERE interface.interface_id = selected_interface_id;
        RETURN;
    END IF;

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

-- Preserve the latest affected-only scheduler by renaming the active function
-- object rather than restating its body here. Migration 211 is applied once by
-- the immutable migration installer, so this rename is deterministic.
ALTER FUNCTION execution.reduce_numeric_pnf_document_frontiers(TEXT, TEXT)
    RENAME TO reduce_numeric_pnf_document_frontiers_affected_scheduler_v210;

CREATE FUNCTION execution.reduce_numeric_pnf_document_frontiers(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    reduced_count BIGINT;
    prior_force TEXT;
BEGIN
    prior_force := current_setting('sensiblaw.force_frontier_rebuild', true);
    PERFORM set_config('sensiblaw.force_frontier_rebuild', 'on', true);

    SELECT execution.reduce_numeric_pnf_document_frontiers_affected_scheduler_v210(
        selected_run_ref,
        selected_document_ref
    )
      INTO reduced_count;

    PERFORM set_config(
        'sensiblaw.force_frontier_rebuild',
        COALESCE(NULLIF(prior_force, ''), 'off'),
        true
    );
    RETURN reduced_count;
EXCEPTION WHEN OTHERS THEN
    PERFORM set_config(
        'sensiblaw.force_frontier_rebuild',
        COALESCE(NULLIF(prior_force, ''), 'off'),
        true
    );
    RAISE;
END;
$$;

COMMENT ON FUNCTION execution.rebuild_numeric_pnf_parent_frontier(BIGINT) IS
    'Canonical parent-frontier API. Under sensiblaw.defer_frontier_rebuild it performs zero publication writes unless an explicit document publication barrier forces reduction.';
COMMENT ON FUNCTION execution.reduce_numeric_pnf_document_frontiers(TEXT, TEXT) IS
    'C3e stable document publication barrier. Forces canonical parent publication while delegating unchanged to the exact affected-only scheduler inherited from migrations 197--210.';
COMMENT ON FUNCTION execution.reduce_numeric_pnf_document_frontiers_affected_scheduler_v210(TEXT, TEXT) IS
    'Frozen implementation object inherited by migration 211 from the previously active affected-only/receipt-driven document frontier scheduler.';

COMMIT;
