BEGIN;

-- C3e/systemic hierarchy orchestration ---------------------------------------
--
-- The Python hierarchy planner already declares sensiblaw.defer_frontier_rebuild
-- while it constructs paragraph/adaptive/document topology, but the canonical
-- rebuild API historically ignored that declaration.  Consequently every
-- parent shell synchronously reduced its frontier and the planner then invoked
-- reduce_numeric_pnf_document_frontiers again at the intended publication
-- barriers.  Make the existing defer contract real: shell construction is a
-- topology operation, while the document reducer temporarily forces semantic
-- publication for one bottom-up batch.
--
-- This changes execution scheduling only.  The canonical delta-native reducer
-- remains the sole producer of parent exports, actor summaries, resolutions,
-- and lookup state.

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

    -- A topology builder may ask for the historical return shape while
    -- explicitly deferring semantic publication.  Return the already-published
    -- summary and perform zero frontier writes.  The document-level barrier
    -- below sets force_frontier_rebuild while it owns publication.
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

CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
    reduced_count BIGINT := 0;
    selected_run_id BIGINT;
    selected_document_id BIGINT;
    started_at TIMESTAMPTZ := clock_timestamp();
    prior_force TEXT;
BEGIN
    SELECT run_id INTO selected_run_id
      FROM execution.semantic_pnf_run_identity
     WHERE run_ref = selected_run_ref;
    SELECT document_id INTO selected_document_id
      FROM execution.semantic_pnf_document_identity
     WHERE document_ref = selected_document_ref;

    prior_force := current_setting('sensiblaw.force_frontier_rebuild', true);
    PERFORM set_config('sensiblaw.force_frontier_rebuild', 'on', true);

    -- Keep the existing semantic ordering: lowest closed region kinds publish
    -- before their parents.  The important change is that this server-side
    -- barrier is now the only place that forces publication while topology is
    -- being materialized; individual shell closes no longer do the same work.
    FOR selected IN
        SELECT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND region.region_kind IN (3, 5, 6, 7, 8, 10)
           AND interface.closure_state IN (2, 3)
         ORDER BY region.region_kind,
                  region.sequence_no,
                  interface.interface_id
    LOOP
        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected.interface_id
          );
        reduced_count := reduced_count + 1;
    END LOOP;

    PERFORM set_config(
        'sensiblaw.force_frontier_rebuild',
        COALESCE(NULLIF(prior_force, ''), 'off'),
        true
    );

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'sparse_frontier_reduction',
        reduced_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

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
    'Canonical parent-frontier API. Under sensiblaw.defer_frontier_rebuild it performs zero publication writes unless a document publication barrier explicitly forces reduction.';
COMMENT ON FUNCTION execution.reduce_numeric_pnf_document_frontiers(TEXT, TEXT) IS
    'C3e document publication barrier: forces the canonical delta-native parent reducer bottom-up while per-parent topology closes remain deferred.';

COMMIT;
