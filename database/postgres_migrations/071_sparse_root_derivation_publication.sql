BEGIN;

-- Restore the sparse-fibre publication boundary after the benchmark-only
-- demand-planner migration.  Existing upgraded databases may have applied the
-- later-added 062_demand_planner_performance.sql after 062_sparse_fibred_...
-- and therefore carry its all-closed-interface refresh function.  Fresh and
-- upgraded databases must converge on the same root-only contract.
CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_ids(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    root_interface_id BIGINT;
    affected_count BIGINT := 0;
    inserted_count BIGINT := 0;
    started_at TIMESTAMPTZ := clock_timestamp();
BEGIN
    PERFORM set_config('work_mem', '256MB', true);

    SELECT interface.interface_id
      INTO root_interface_id
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND region.region_kind = 10
       AND interface.closure_state IN (2, 3)
     ORDER BY interface.interface_id
     LIMIT 1;

    IF root_interface_id IS NULL THEN
        RETURN 0;
    END IF;

    -- Remove every historical non-root projection and any root row no longer
    -- admitted by the sparse document frontier.
    DELETE FROM execution.semantic_pnf_global_lookup AS global
     WHERE global.run_id = selected_run_id
       AND global.document_id = selected_document_id
       AND (
           global.interface_id <> root_interface_id
           OR NOT EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_interface_lookup AS lookup
                WHERE lookup.interface_id = root_interface_id
                  AND lookup.key_kind = global.key_kind
                  AND lookup.key_a = global.key_a
                  AND lookup.key_b = global.key_b
                  AND lookup.target_kind = global.target_kind
                  AND lookup.target_id = global.target_id
           )
       );
    GET DIAGNOSTICS affected_count = ROW_COUNT;

    INSERT INTO execution.semantic_pnf_global_lookup
        (run_ref, document_ref, run_id, document_id,
         interface_id, region_id, region_kind,
         region_start_char, region_end_char,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT region.run_ref,
           region.document_ref,
           region.run_id,
           region.document_id,
           root_interface_id,
           region.region_id,
           region.region_kind,
           region.start_char,
           region.end_char,
           lookup.key_kind,
           lookup.key_a,
           lookup.key_b,
           lookup.target_kind,
           lookup.target_id,
           lookup.rank
      FROM execution.semantic_pnf_interface_lookup AS lookup
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = root_interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE lookup.interface_id = root_interface_id
    ON CONFLICT (
        interface_id, key_kind, key_a, key_b,
        target_kind, target_id
    ) DO UPDATE SET
        rank = EXCLUDED.rank,
        region_id = EXCLUDED.region_id,
        region_kind = EXCLUDED.region_kind,
        region_start_char = EXCLUDED.region_start_char,
        region_end_char = EXCLUDED.region_end_char,
        run_id = EXCLUDED.run_id,
        document_id = EXCLUDED.document_id,
        run_ref = EXCLUDED.run_ref,
        document_ref = EXCLUDED.document_ref;
    GET DIAGNOSTICS inserted_count = ROW_COUNT;

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'root_global_lookup_refresh',
        inserted_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    RETURN inserted_count + affected_count;
END;
$$;

-- Publication now has an explicit proof-derivation phase.  It derives identity
-- substitutions and bounded factor-composition candidates only after local
-- frontiers have closed and before the final root projection is reported.
CREATE OR REPLACE FUNCTION execution.refresh_pnf_visible_lookup(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_run_id BIGINT;
    selected_document_id BIGINT;
    root_interface_id BIGINT;
    inserted_count BIGINT := 0;
    derivation_count BIGINT := 0;
    started_at TIMESTAMPTZ := clock_timestamp();
    derivation_started_at TIMESTAMPTZ;
    derivation_row RECORD;
BEGIN
    PERFORM execution.reduce_numeric_pnf_document_frontiers(
        selected_run_ref,
        selected_document_ref
    );

    SELECT run_id INTO selected_run_id
      FROM execution.semantic_pnf_run_identity
     WHERE run_ref = selected_run_ref;
    SELECT document_id INTO selected_document_id
      FROM execution.semantic_pnf_document_identity
     WHERE document_ref = selected_document_ref;

    derivation_started_at := clock_timestamp();
    SELECT *
      INTO derivation_row
      FROM execution.refresh_numeric_pnf_semantic_derivations(
          selected_run_id,
          selected_document_id
      );
    derivation_count :=
        COALESCE(derivation_row.identity_witness_count, 0)
        + COALESCE(derivation_row.identity_derivation_count, 0)
        + COALESCE(derivation_row.composition_candidate_count, 0);

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'proof_relevant_derivations',
        derivation_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - derivation_started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    SELECT interface.interface_id
      INTO root_interface_id
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND region.region_kind = 10
       AND interface.closure_state IN (2, 3)
     ORDER BY interface.interface_id
     LIMIT 1;

    DELETE FROM execution.semantic_pnf_visible_lookup AS visible
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
    WHERE visible.interface_id = interface.interface_id
      AND interface.region_id = region.region_id
      AND region.run_id = selected_run_id
      AND region.document_id = selected_document_id;

    IF root_interface_id IS NOT NULL THEN
        INSERT INTO execution.semantic_pnf_visible_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, source_interface_id,
             ancestor_distance, rank)
        SELECT root_interface_id,
               lookup.key_kind,
               lookup.key_a,
               lookup.key_b,
               lookup.target_kind,
               lookup.target_id,
               root_interface_id,
               0,
               lookup.rank
          FROM execution.semantic_pnf_interface_lookup AS lookup
         WHERE lookup.interface_id = root_interface_id
        ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS inserted_count = ROW_COUNT;
    END IF;

    PERFORM execution.refresh_pnf_global_lookup_ids(
        selected_run_id,
        selected_document_id
    );

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'root_visible_projection',
        inserted_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    RETURN inserted_count;
END;
$$;

COMMIT;
