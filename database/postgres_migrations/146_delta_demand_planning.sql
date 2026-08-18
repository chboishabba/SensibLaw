BEGIN;

-- 146: preserve the full hierarchy publication boundary while making the
-- post-adjacency publication demand-local as well as lookup-local.
--
-- Migration 145 reduced the physical lookup refresh to changed paragraph-pair
-- interfaces, but the existing AFTER INSERT statement trigger still invoked the
-- whole-document demand planner. Factor the exact per-demand candidate kernel
-- once, retain the existing full scheduler for authoritative hierarchy refresh,
-- and add an interface-indexed scheduler for the final adjacency delta.

CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_one_demand(
    selected_demand_id BIGINT,
    anaphor_residual_id BIGINT,
    pronoun_kind_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    demand_row RECORD;
    inserted_for_demand BIGINT := 0;
BEGIN
    SELECT demand.*,
           source_region.run_ref AS source_run_ref,
           source_region.document_ref AS source_document_ref
      INTO demand_row
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = demand.source_region_id
     WHERE demand.demand_id = selected_demand_id
       AND demand.state IN (1, 2);

    IF demand_row.demand_id IS NULL THEN
        RETURN 0;
    END IF;

    DELETE FROM execution.semantic_pnf_demand_candidate
     WHERE demand_id = demand_row.demand_id;

    INSERT INTO execution.semantic_pnf_demand_candidate
        (demand_id, ordinal, target_kind, target_id,
         source_interface_id, ancestor_distance,
         index_rank, candidate_score)
    SELECT demand_row.demand_id,
           row_number() OVER (
               ORDER BY candidate.structural_distance,
                        candidate.index_rank,
                        candidate.target_id
           ) - 1,
           candidate.target_kind,
           candidate.target_id,
           candidate.source_interface_id,
           candidate.structural_distance,
           candidate.index_rank,
           candidate.candidate_score
      FROM LATERAL (
          SELECT DISTINCT ON (global.target_kind, global.target_id)
                 global.target_kind,
                 global.target_id,
                 global.interface_id AS source_interface_id,
                 abs(
                     COALESCE(demand_row.source_start_char, 0)
                     - global.region_end_char
                 ) AS structural_distance,
                 global.rank AS index_rank,
                 COALESCE(object.promotion_score, factor.support_score, 0)
                     AS candidate_score
            FROM execution.semantic_pnf_global_lookup AS global
            LEFT JOIN execution.semantic_pnf_object AS object
              ON global.target_kind = 1
             AND object.object_id = global.target_id
            LEFT JOIN execution.semantic_pnf_factor AS factor
              ON global.target_kind = 2
             AND factor.factor_id = global.target_id
           WHERE global.run_ref = demand_row.source_run_ref
             AND global.document_ref = demand_row.source_document_ref
             AND global.target_kind = demand_row.expected_target_kind
             AND global.target_id <> demand_row.demand_id
             AND (
                 (
                     demand_row.residual_type_symbol_id = anaphor_residual_id
                     AND global.target_kind = 1
                     AND global.region_id <> demand_row.source_region_id
                     AND (
                         pronoun_kind_id IS NULL
                         OR object.object_kind_symbol_id <> pronoun_kind_id
                     )
                     AND global.region_end_char
                         <= COALESCE(
                             demand_row.source_start_char,
                             global.region_end_char
                         )
                 )
                 OR (
                     demand_row.expected_factor_type_symbol_id IS NOT NULL
                     AND global.key_kind = 1
                     AND global.key_a
                         = demand_row.expected_factor_type_symbol_id
                 )
                 OR (
                     demand_row.expected_object_kind_symbol_id IS NOT NULL
                     AND global.key_kind = 2
                     AND global.key_a
                         = demand_row.expected_object_kind_symbol_id
                 )
                 OR (
                     demand_row.lexical_symbol_id IS NOT NULL
                     AND global.key_kind = 3
                     AND global.key_a = demand_row.lexical_symbol_id
                 )
                 OR (
                     global.key_kind = 5
                     AND global.key_a = demand_row.residual_type_symbol_id
                 )
             )
           ORDER BY global.target_kind,
                    global.target_id,
                    structural_distance,
                    global.rank
           LIMIT demand_row.max_candidates
      ) AS candidate;

    GET DIAGNOSTICS inserted_for_demand = ROW_COUNT;
    UPDATE execution.semantic_pnf_demand
       SET candidate_count = inserted_for_demand,
           state = CASE
               WHEN inserted_for_demand > 0 THEN 2
               ELSE state
           END
     WHERE demand_id = demand_row.demand_id;

    RETURN inserted_for_demand;
END;
$$;

CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
    inserted_total BIGINT := 0;
    anaphor_residual_id BIGINT;
    pronoun_kind_id BIGINT;
BEGIN
    SELECT symbol_id
      INTO anaphor_residual_id
      FROM execution.semantic_symbol
     WHERE kind_id = 13
       AND symbol_text = 'anaphor_unresolved';
    SELECT symbol_id
      INTO pronoun_kind_id
      FROM execution.semantic_symbol
     WHERE kind_id = 14
       AND symbol_text = 'mention.pronoun';

    FOR selected IN
        SELECT demand.demand_id
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE source_region.run_ref = selected_run_ref
           AND source_region.document_ref = selected_document_ref
           AND demand.source_interface_id IS NOT NULL
           AND demand.state IN (1, 2)
         ORDER BY demand.demand_id
    LOOP
        inserted_total := inserted_total
            + execution.plan_numeric_pnf_one_demand(
                selected.demand_id,
                anaphor_residual_id,
                pronoun_kind_id
            );
    END LOOP;

    UPDATE execution.semantic_pnf_demand AS demand
       SET state = 3
      FROM execution.semantic_pnf_region AS source_region
     WHERE source_region.region_id = demand.source_region_id
       AND source_region.run_ref = selected_run_ref
       AND source_region.document_ref = selected_document_ref
       AND demand.state = 1
       AND demand.candidate_count = 0
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_region AS document_region
            WHERE document_region.run_ref = selected_run_ref
              AND document_region.document_ref = selected_document_ref
              AND document_region.region_kind = 10
              AND document_region.closure_state = 3
       );
    RETURN inserted_total;
END;
$$;

CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_for_interfaces(
    selected_run_ref TEXT,
    selected_document_ref TEXT,
    selected_interface_ids BIGINT[]
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_demand_id BIGINT;
    affected_ids BIGINT[];
    inserted_total BIGINT := 0;
    anaphor_residual_id BIGINT;
    pronoun_kind_id BIGINT;
BEGIN
    IF selected_interface_ids IS NULL
       OR cardinality(selected_interface_ids) = 0 THEN
        RETURN 0;
    END IF;

    SELECT symbol_id
      INTO anaphor_residual_id
      FROM execution.semantic_symbol
     WHERE kind_id = 13
       AND symbol_text = 'anaphor_unresolved';
    SELECT symbol_id
      INTO pronoun_kind_id
      FROM execution.semantic_symbol
     WHERE kind_id = 14
       AND symbol_text = 'mention.pronoun';

    SELECT COALESCE(
               array_agg(DISTINCT demand.demand_id ORDER BY demand.demand_id),
               ARRAY[]::BIGINT[]
           )
      INTO affected_ids
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = demand.source_region_id
     WHERE source_region.run_ref = selected_run_ref
       AND source_region.document_ref = selected_document_ref
       AND demand.source_interface_id IS NOT NULL
       AND demand.state IN (1, 2)
       AND (
           EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_demand_candidate AS existing
                WHERE existing.demand_id = demand.demand_id
                  AND existing.source_interface_id = ANY(selected_interface_ids)
           )
           OR EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_global_lookup AS global
                 LEFT JOIN execution.semantic_pnf_object AS object
                   ON global.target_kind = 1
                  AND object.object_id = global.target_id
                WHERE global.interface_id = ANY(selected_interface_ids)
                  AND global.run_ref = selected_run_ref
                  AND global.document_ref = selected_document_ref
                  AND global.target_kind = demand.expected_target_kind
                  AND global.target_id <> demand.demand_id
                  AND (
                      (
                          demand.residual_type_symbol_id = anaphor_residual_id
                          AND global.target_kind = 1
                          AND global.region_id <> demand.source_region_id
                          AND (
                              pronoun_kind_id IS NULL
                              OR object.object_kind_symbol_id <> pronoun_kind_id
                          )
                          AND global.region_end_char
                              <= COALESCE(
                                  demand.source_start_char,
                                  global.region_end_char
                              )
                      )
                      OR (
                          demand.expected_factor_type_symbol_id IS NOT NULL
                          AND global.key_kind = 1
                          AND global.key_a = demand.expected_factor_type_symbol_id
                      )
                      OR (
                          demand.expected_object_kind_symbol_id IS NOT NULL
                          AND global.key_kind = 2
                          AND global.key_a = demand.expected_object_kind_symbol_id
                      )
                      OR (
                          demand.lexical_symbol_id IS NOT NULL
                          AND global.key_kind = 3
                          AND global.key_a = demand.lexical_symbol_id
                      )
                      OR (
                          global.key_kind = 5
                          AND global.key_a = demand.residual_type_symbol_id
                      )
                  )
           )
       );

    FOREACH selected_demand_id IN ARRAY affected_ids LOOP
        inserted_total := inserted_total
            + execution.plan_numeric_pnf_one_demand(
                selected_demand_id,
                anaphor_residual_id,
                pronoun_kind_id
            );
    END LOOP;

    UPDATE execution.semantic_pnf_demand AS demand
       SET state = 3
     WHERE demand.demand_id = ANY(affected_ids)
       AND demand.state = 1
       AND demand.candidate_count = 0
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_region AS document_region
            WHERE document_region.run_ref = selected_run_ref
              AND document_region.document_ref = selected_document_ref
              AND document_region.region_kind = 10
              AND document_region.closure_state = 3
       );

    RETURN inserted_total;
END;
$$;

-- Delta publication calls its targeted planner explicitly. Suppress the normal
-- full-document statement-trigger planner only inside that transaction-local
-- call boundary.
CREATE OR REPLACE FUNCTION execution.plan_demands_after_global_lookup_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
BEGIN
    IF current_setting('sensiblaw.delta_global_lookup_refresh', TRUE) = 'on' THEN
        RETURN NULL;
    END IF;

    FOR selected IN
        SELECT DISTINCT run_ref, document_ref
          FROM inserted_global
    LOOP
        PERFORM execution.plan_numeric_pnf_demand_candidates(
            selected.run_ref,
            selected.document_ref
        );
    END LOOP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_interfaces(
    selected_run_ref TEXT,
    selected_document_ref TEXT,
    selected_interface_ids BIGINT[]
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count BIGINT := 0;
    inserted_count BIGINT := 0;
BEGIN
    IF selected_interface_ids IS NULL
       OR cardinality(selected_interface_ids) = 0 THEN
        RETURN 0;
    END IF;

    WITH selected AS (
        SELECT DISTINCT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE interface.interface_id = ANY(selected_interface_ids)
           AND region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
    )
    DELETE FROM execution.semantic_pnf_global_lookup AS global
    USING selected
    WHERE global.interface_id = selected.interface_id
      AND global.run_ref = selected_run_ref
      AND global.document_ref = selected_document_ref;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- The INSERT statement trigger still fires, but observes this transaction-
    -- local flag and performs no whole-document planning.
    PERFORM set_config('sensiblaw.delta_global_lookup_refresh', 'on', TRUE);

    WITH selected AS (
        SELECT DISTINCT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE interface.interface_id = ANY(selected_interface_ids)
           AND region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND interface.closure_state IN (2, 3)
    )
    INSERT INTO execution.semantic_pnf_global_lookup
        (run_ref, document_ref, interface_id, region_id, region_kind,
         region_start_char, region_end_char,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT region.run_ref,
           region.document_ref,
           lookup.interface_id,
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
      FROM selected
      JOIN execution.semantic_pnf_interface_lookup AS lookup
        ON lookup.interface_id = selected.interface_id
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = selected.interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    PERFORM set_config('sensiblaw.delta_global_lookup_refresh', 'off', TRUE);

    PERFORM execution.plan_numeric_pnf_demand_candidates_for_interfaces(
        selected_run_ref,
        selected_document_ref,
        selected_interface_ids
    );

    RETURN inserted_count - deleted_count;
END;
$$;

COMMIT;
