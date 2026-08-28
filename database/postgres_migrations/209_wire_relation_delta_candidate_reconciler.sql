BEGIN;

-- C3d integration: make the reusable 208 desired/current reconciler the sole
-- candidate mutation owner of the active affected-parent reducer.  The
-- historical document-wide planner remains available for compatibility, but
-- the live 206 parent path must not retain its delete/reinsert block.

CREATE OR REPLACE FUNCTION execution.reconcile_numeric_pnf_parent_candidates(
    selected_interface_id BIGINT,
    selected_region_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    desired_total BIGINT := 0;
    current_before BIGINT := 0;
    added_total BIGINT := 0;
    removed_total BIGINT := 0;
    replaced_total BIGINT := 0;
    unchanged_total BIGINT := 0;
    mutation_statements SMALLINT := 0;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS pg_temp.numeric_pnf_desired_parent_candidate (
        demand_id BIGINT NOT NULL,
        ordinal SMALLINT NOT NULL,
        target_kind SMALLINT NOT NULL,
        target_id BIGINT NOT NULL,
        source_interface_id BIGINT NOT NULL,
        ancestor_distance BIGINT NOT NULL,
        index_rank BIGINT NOT NULL,
        candidate_score DOUBLE PRECISION NOT NULL,
        common_scope_interface_id BIGINT,
        validation_state SMALLINT,
        PRIMARY KEY (demand_id, target_kind, target_id)
    ) ON COMMIT DROP;
    TRUNCATE pg_temp.numeric_pnf_desired_parent_candidate;

    WITH parent_demand AS (
        SELECT demand.*,
               COALESCE(demand.source_start_char, source_region.end_char)
                   AS demand_position,
               source_region.start_char AS source_region_start,
               source_region.end_char AS source_region_end
          FROM execution.semantic_pnf_parent_affected_key AS key
          JOIN execution.semantic_pnf_interface_export AS demand_export
            ON demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand_export.target_id = key.key_a
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE key.parent_region_id = selected_region_id
           AND key.key_family = 3
           AND demand.state IN (1, 3)
    ),
    object_candidate AS (
        SELECT demand.demand_id, 1::SMALLINT AS target_kind,
               profile.object_id AS target_id,
               selected_interface_id AS source_interface_id,
               abs(demand.demand_position - profile.last_end_char)
                   AS structural_distance,
               0::BIGINT AS index_rank,
               profile.promotion_score
                   + ln(1 + profile.occurrence_count)::DOUBLE PRECISION
                   AS candidate_score
          FROM parent_demand AS demand
          JOIN execution.semantic_pnf_actor_profile AS profile
            ON profile.interface_id = selected_interface_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = profile.object_id
         WHERE demand.expected_target_kind = 1
           AND (demand.expected_object_kind_symbol_id IS NULL
                OR demand.expected_object_kind_symbol_id = profile.object_kind_symbol_id)
           AND (demand.role_symbol_id IS NULL
                OR demand.role_symbol_id = profile.role_symbol_id)
           AND (demand.expected_factor_type_symbol_id IS NULL
                OR demand.expected_factor_type_symbol_id = profile.factor_type_symbol_id)
           AND (demand.lexical_symbol_id IS NULL
                OR demand.lexical_symbol_id = object.head_symbol_id
                OR demand.lexical_symbol_id = profile.predicate_symbol_id)
           AND CASE demand.recency_class
               WHEN 1 THEN profile.first_start_char >= demand.source_region_start
                         AND profile.last_end_char <= demand.source_region_end
               WHEN 2 THEN profile.last_end_char <= demand.demand_position
               WHEN 3 THEN profile.last_end_char <= demand.demand_position
               WHEN 4 THEN TRUE
               WHEN 5 THEN TRUE
               ELSE FALSE
           END
    ),
    factor_candidate AS (
        SELECT demand.demand_id, 2::SMALLINT AS target_kind,
               factor.factor_id AS target_id,
               selected_interface_id AS source_interface_id,
               abs(demand.demand_position - factor_region.end_char)
                   AS structural_distance,
               factor_export.rank AS index_rank,
               factor.support_score AS candidate_score
          FROM parent_demand AS demand
          JOIN execution.semantic_pnf_interface_export AS factor_export
            ON factor_export.interface_id = selected_interface_id
           AND factor_export.target_kind = 2
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = factor_export.target_id
          JOIN execution.semantic_pnf_region AS factor_region
            ON factor_region.region_id = factor.region_id
         WHERE demand.expected_target_kind = 2
           AND (demand.expected_factor_type_symbol_id IS NULL
                OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id)
           AND (demand.lexical_symbol_id IS NULL
                OR demand.lexical_symbol_id = factor.predicate_symbol_id)
           AND (demand.recency_class IN (4, 5)
                OR factor_region.end_char <= demand.demand_position)
    ),
    deduplicated AS (
        SELECT candidate.*,
               row_number() OVER (
                   PARTITION BY candidate.demand_id, candidate.target_kind,
                                candidate.target_id
                   ORDER BY candidate.structural_distance,
                            candidate.candidate_score DESC,
                            candidate.index_rank,
                            candidate.source_interface_id
               ) AS target_occurrence
          FROM (
              SELECT * FROM object_candidate
              UNION ALL
              SELECT * FROM factor_candidate
          ) AS candidate
    ),
    ranked AS (
        SELECT candidate.*,
               row_number() OVER (
                   PARTITION BY candidate.demand_id
                   ORDER BY candidate.structural_distance,
                            candidate.candidate_score DESC,
                            candidate.index_rank,
                            candidate.target_id
               ) - 1 AS candidate_ordinal
          FROM deduplicated AS candidate
         WHERE candidate.target_occurrence = 1
    )
    INSERT INTO pg_temp.numeric_pnf_desired_parent_candidate
        (demand_id, ordinal, target_kind, target_id, source_interface_id,
         ancestor_distance, index_rank, candidate_score,
         common_scope_interface_id, validation_state)
    SELECT ranked.demand_id, ranked.candidate_ordinal::SMALLINT,
           ranked.target_kind, ranked.target_id, ranked.source_interface_id,
           ranked.structural_distance, ranked.index_rank,
           ranked.candidate_score, selected_interface_id, 2
      FROM ranked
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = ranked.demand_id
     WHERE ranked.candidate_ordinal < demand.max_candidates;

    SELECT count(*) INTO desired_total
      FROM pg_temp.numeric_pnf_desired_parent_candidate;
    SELECT count(*) INTO current_before
      FROM execution.semantic_pnf_demand_candidate AS candidate
     WHERE EXISTS (
         SELECT 1
           FROM execution.semantic_pnf_parent_affected_key AS key
          WHERE key.parent_region_id = selected_region_id
            AND key.key_family = 3
            AND key.key_a = candidate.demand_id
     );

    WITH doomed AS (
        SELECT candidate.demand_id, candidate.target_kind, candidate.target_id
          FROM execution.semantic_pnf_demand_candidate AS candidate
         WHERE EXISTS (
             SELECT 1
               FROM execution.semantic_pnf_parent_affected_key AS key
              WHERE key.parent_region_id = selected_region_id
                AND key.key_family = 3
                AND key.key_a = candidate.demand_id
         )
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_temp.numeric_pnf_desired_parent_candidate AS desired
                WHERE desired.demand_id = candidate.demand_id
                  AND desired.target_kind = candidate.target_kind
                  AND desired.target_id = candidate.target_id
                  AND ROW(candidate.ordinal, candidate.source_interface_id,
                          candidate.ancestor_distance, candidate.index_rank,
                          candidate.candidate_score,
                          candidate.common_scope_interface_id,
                          candidate.validation_state)
                      IS NOT DISTINCT FROM
                      ROW(desired.ordinal, desired.source_interface_id,
                          desired.ancestor_distance, desired.index_rank,
                          desired.candidate_score,
                          desired.common_scope_interface_id,
                          desired.validation_state)
           )
    )
    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate
     USING doomed
     WHERE candidate.demand_id = doomed.demand_id
       AND candidate.target_kind = doomed.target_kind
       AND candidate.target_id = doomed.target_id;
    GET DIAGNOSTICS removed_total = ROW_COUNT;
    IF removed_total > 0 THEN mutation_statements := mutation_statements + 1; END IF;

    SELECT count(*) INTO replaced_total
      FROM execution.semantic_pnf_demand_candidate AS candidate
      JOIN pg_temp.numeric_pnf_desired_parent_candidate AS desired
        ON desired.demand_id = candidate.demand_id
       AND desired.target_kind = candidate.target_kind
       AND desired.target_id = candidate.target_id
     WHERE EXISTS (
         SELECT 1 FROM execution.semantic_pnf_parent_affected_key AS key
          WHERE key.parent_region_id = selected_region_id
            AND key.key_family = 3 AND key.key_a = candidate.demand_id
     )
       AND ROW(candidate.ordinal, candidate.source_interface_id,
               candidate.ancestor_distance, candidate.index_rank,
               candidate.candidate_score, candidate.common_scope_interface_id,
               candidate.validation_state)
           IS DISTINCT FROM
           ROW(desired.ordinal, desired.source_interface_id,
               desired.ancestor_distance, desired.index_rank,
               desired.candidate_score, desired.common_scope_interface_id,
               desired.validation_state);

    INSERT INTO execution.semantic_pnf_demand_candidate
        (demand_id, ordinal, target_kind, target_id, source_interface_id,
         ancestor_distance, index_rank, candidate_score,
         common_scope_interface_id, validation_state)
    SELECT desired.demand_id, desired.ordinal, desired.target_kind,
           desired.target_id, desired.source_interface_id,
           desired.ancestor_distance, desired.index_rank, desired.candidate_score,
           desired.common_scope_interface_id, desired.validation_state
      FROM pg_temp.numeric_pnf_desired_parent_candidate AS desired
     WHERE NOT EXISTS (
         SELECT 1
           FROM execution.semantic_pnf_demand_candidate AS candidate
          WHERE candidate.demand_id = desired.demand_id
            AND candidate.target_kind = desired.target_kind
            AND candidate.target_id = desired.target_id
            AND candidate.ordinal = desired.ordinal
            AND candidate.source_interface_id = desired.source_interface_id
            AND candidate.ancestor_distance = desired.ancestor_distance
            AND candidate.index_rank = desired.index_rank
            AND candidate.candidate_score = desired.candidate_score
            AND candidate.common_scope_interface_id IS NOT DISTINCT FROM desired.common_scope_interface_id
            AND candidate.validation_state IS NOT DISTINCT FROM desired.validation_state
     );
    GET DIAGNOSTICS added_total = ROW_COUNT;
    IF added_total > 0 THEN mutation_statements := mutation_statements + 1; END IF;

    unchanged_total := desired_total - added_total - replaced_total;

    INSERT INTO execution.semantic_relation_reconciliation_receipt
        (owner_ref, scope_a, scope_b, desired_rows, current_rows_before,
         added_rows, removed_rows, replaced_rows, unchanged_rows_skipped,
         physical_row_mutations, mutation_statements, semantic_authority_effect)
    VALUES (
        'execution.reduce_numeric_pnf_parent_frontier_affected.candidates',
        selected_region_id, selected_interface_id, desired_total, current_before,
        added_total, removed_total, replaced_total, unchanged_total,
        added_total + removed_total + 2 * replaced_total,
        mutation_statements, 'none'
    );
END;
$$;

-- Replace only the active 206 candidate mutation block.  This is intentionally
-- fail-closed: if 206's canonical block has changed, migration composition
-- must stop instead of creating two candidate authorities.
DO $$
DECLARE
    definition TEXT;
    block_start INTEGER;
    block_end INTEGER;
    replacement TEXT :=
        '    PERFORM execution.reconcile_numeric_pnf_parent_candidates(' ||
        'selected_interface_id, selected_region_id);' || E'\n\n';
BEGIN
    SELECT pg_get_functiondef(
        'execution.reduce_numeric_pnf_parent_frontier_affected(bigint)'::regprocedure
    ) INTO definition;
    block_start := position(
        '    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate'
        IN definition
    );
    block_end := position(
        '    WITH affected_demand AS ('
        IN substring(definition FROM block_start)
    );
    IF block_start = 0 OR block_end = 0 THEN
        RAISE EXCEPTION
            '209 refused to patch active 206 candidate block: canonical markers absent';
    END IF;
    block_end := block_start + block_end - 1;
    definition := left(definition, block_start - 1)
        || replacement
        || substring(definition FROM block_end);
    EXECUTE definition;
END;
$$;

COMMENT ON FUNCTION execution.reconcile_numeric_pnf_parent_candidates(BIGINT, BIGINT) IS
    'C3d sole active candidate mutation owner: desired/current relation reconciliation for one affected parent fibre.';

COMMIT;
