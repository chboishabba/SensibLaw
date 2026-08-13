BEGIN;

-- Add index on (run_id, document_id, start_char, end_char, closure_state) to optimize
-- set-based candidate common-scope region lookups.
CREATE INDEX IF NOT EXISTS semantic_pnf_region_numeric_span_idx
    ON execution.semantic_pnf_region
       (run_id, document_id, start_char, end_char, closure_state);

CREATE INDEX IF NOT EXISTS semantic_pnf_region_numeric_end_char_idx
    ON execution.semantic_pnf_region
       (run_id, document_id, end_char DESC);

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_numeric_region_idx
    ON execution.semantic_pnf_demand
       (source_region_id, state);

-- Redefine refresh_pnf_global_lookup_ids with 256MB work_mem for sort/merge during bulk insertion.
CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_ids(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_count BIGINT;
BEGIN
    PERFORM set_config('work_mem', '256MB', true);

    DELETE FROM execution.semantic_pnf_global_lookup
     WHERE run_id = selected_run_id
       AND document_id = selected_document_id;

    INSERT INTO execution.semantic_pnf_global_lookup
        (run_ref, document_ref, run_id, document_id,
         interface_id, region_id, region_kind,
         region_start_char, region_end_char,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT region.run_ref,
           region.document_ref,
           region.run_id,
           region.document_id,
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
      FROM execution.semantic_pnf_interface_lookup AS lookup
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = lookup.interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND interface.closure_state IN (2, 3)
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count;
END;
$$;

-- Optimize plan_numeric_pnf_demand_candidates_ids:
-- 1. LATERAL top-K index lookup for anaphor demands to eliminate 48-million-row Cartesian cross-join.
-- 2. Filter bounded_top by max_candidates BEFORE evaluating common_scope LATERAL joins.
CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_ids(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_total BIGINT := 0;
    anaphor_residual_id BIGINT;
    pronoun_kind_id BIGINT;
BEGIN
    PERFORM set_config('work_mem', '256MB', true);

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

    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate
    USING execution.semantic_pnf_demand AS demand,
          execution.semantic_pnf_region AS source_region
    WHERE candidate.demand_id = demand.demand_id
      AND source_region.region_id = demand.source_region_id
      AND source_region.run_id = selected_run_id
      AND source_region.document_id = selected_document_id
      AND demand.state IN (1, 2);

    WITH selected_demand AS (
        SELECT demand.demand_id,
               demand.source_interface_id,
               demand.source_region_id,
               demand.expected_target_kind,
               demand.residual_type_symbol_id,
               demand.recency_class,
               demand.max_candidates,
               COALESCE(demand.source_start_char, source_region.end_char)
                   AS demand_position,
               source_region.parent_region_id AS source_parent_region_id,
               source_region.start_char AS source_region_start,
               source_region.end_char AS source_region_end
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE source_region.run_id = selected_run_id
           AND source_region.document_id = selected_document_id
           AND demand.source_interface_id IS NOT NULL
           AND demand.state IN (1, 2)
    ),
    exact_match AS (
        SELECT demand.demand_id,
               demand.source_interface_id,
               demand.source_region_id,
               demand.recency_class,
               demand.max_candidates,
               demand.demand_position,
               demand.source_parent_region_id,
               demand.source_region_start,
               demand.source_region_end,
               global.target_kind,
               global.target_id,
               COALESCE(origin_interface.interface_id, global.interface_id)
                   AS candidate_interface_id,
               origin_region.region_id AS candidate_region_id,
               origin_region.parent_region_id AS candidate_parent_region_id,
               origin_region.start_char AS candidate_region_start,
               origin_region.end_char AS candidate_region_end,
               abs(demand.demand_position - origin_region.end_char)
                   AS structural_distance,
               global.rank AS index_rank,
               COALESCE(object.promotion_score, factor.support_score, 0)
                   AS candidate_score,
               global.region_end_char - global.region_start_char
                   AS export_scope_width
          FROM selected_demand AS demand
          JOIN execution.semantic_pnf_demand_lookup_key AS demand_key
            ON demand_key.demand_id = demand.demand_id
          JOIN execution.semantic_pnf_global_lookup AS global
            ON global.run_id = selected_run_id
           AND global.document_id = selected_document_id
           AND global.key_kind = demand_key.key_kind
           AND global.key_a = demand_key.key_a
           AND global.key_b = demand_key.key_b
           AND global.target_kind = demand_key.target_kind
          LEFT JOIN execution.semantic_pnf_object AS object
            ON global.target_kind = 1
           AND object.object_id = global.target_id
          LEFT JOIN execution.semantic_pnf_factor AS factor
            ON global.target_kind = 2
           AND factor.factor_id = global.target_id
          JOIN execution.semantic_pnf_region AS origin_region
            ON origin_region.region_id = COALESCE(
                object.region_id,
                factor.region_id,
                global.region_id
            )
          LEFT JOIN execution.semantic_pnf_interface AS origin_interface
            ON origin_interface.region_id = origin_region.region_id
    ),
    anaphor_match AS (
        SELECT demand.demand_id,
               demand.source_interface_id,
               demand.source_region_id,
               demand.recency_class,
               demand.max_candidates,
               demand.demand_position,
               demand.source_parent_region_id,
               demand.source_region_start,
               demand.source_region_end,
               cand.target_kind,
               cand.target_id,
               cand.candidate_interface_id,
               cand.candidate_region_id,
               cand.candidate_parent_region_id,
               cand.candidate_region_start,
               cand.candidate_region_end,
               cand.structural_distance,
               cand.index_rank,
               cand.candidate_score,
               cand.export_scope_width
          FROM selected_demand AS demand
          CROSS JOIN LATERAL (
              SELECT global.target_kind,
                     global.target_id,
                     COALESCE(origin_interface.interface_id, global.interface_id)
                         AS candidate_interface_id,
                     origin_region.region_id AS candidate_region_id,
                     origin_region.parent_region_id AS candidate_parent_region_id,
                     origin_region.start_char AS candidate_region_start,
                     origin_region.end_char AS candidate_region_end,
                     (demand.demand_position - origin_region.end_char)
                         AS structural_distance,
                     global.rank AS index_rank,
                     object.promotion_score AS candidate_score,
                     global.region_end_char - global.region_start_char
                         AS export_scope_width
                FROM execution.semantic_pnf_global_lookup AS global
                JOIN execution.semantic_pnf_object AS object
                  ON object.object_id = global.target_id
                JOIN execution.semantic_pnf_region AS origin_region
                  ON origin_region.region_id = object.region_id
                LEFT JOIN execution.semantic_pnf_interface AS origin_interface
                  ON origin_interface.region_id = origin_region.region_id
               WHERE global.run_id = selected_run_id
                 AND global.document_id = selected_document_id
                 AND global.target_kind = 1
                 AND origin_region.region_id <> demand.source_region_id
                 AND origin_region.end_char <= demand.demand_position
                 AND (
                     pronoun_kind_id IS NULL
                     OR object.object_kind_symbol_id <> pronoun_kind_id
                 )
               ORDER BY origin_region.end_char DESC, global.rank
               LIMIT LEAST(demand.max_candidates, 10)
          ) AS cand
         WHERE demand.residual_type_symbol_id = anaphor_residual_id
    ),
    all_match AS (
        SELECT * FROM exact_match
        UNION ALL
        SELECT * FROM anaphor_match
    ),
    target_deduplicated AS (
        SELECT match.*,
               row_number() OVER (
                   PARTITION BY match.demand_id,
                                match.target_kind,
                                match.target_id
                   ORDER BY match.structural_distance,
                            match.export_scope_width,
                            match.index_rank,
                            match.candidate_interface_id
               ) AS target_occurrence
          FROM all_match AS match
    ),
    bounded AS (
        SELECT match.*,
               row_number() OVER (
                   PARTITION BY match.demand_id
                   ORDER BY match.structural_distance,
                            match.index_rank,
                            match.target_id
               ) - 1 AS candidate_ordinal
          FROM target_deduplicated AS match
         WHERE match.target_occurrence = 1
    ),
    bounded_top AS (
        SELECT *
          FROM bounded
         WHERE candidate_ordinal < max_candidates
    ),
    scoped AS (
        SELECT bounded.*,
               common_scope.interface_id AS common_scope_interface_id,
               common_scope.region_kind AS common_scope_region_kind
          FROM bounded_top AS bounded
          LEFT JOIN LATERAL (
              SELECT interface.interface_id,
                     common_region.region_kind
                FROM execution.semantic_pnf_region AS common_region
                JOIN execution.semantic_pnf_interface AS interface
                  ON interface.region_id = common_region.region_id
               WHERE common_region.run_id = selected_run_id
                 AND common_region.document_id = selected_document_id
                 AND common_region.start_char <= LEAST(
                     bounded.source_region_start,
                     bounded.candidate_region_start
                 )
                 AND common_region.end_char >= GREATEST(
                     bounded.source_region_end,
                     bounded.candidate_region_end
                 )
                 AND interface.closure_state IN (2, 3)
               ORDER BY common_region.end_char - common_region.start_char,
                        common_region.region_kind,
                        interface.interface_id
               LIMIT 1
          ) AS common_scope ON TRUE
    ),
    valid AS (
        SELECT scoped.*
          FROM scoped
         WHERE scoped.common_scope_interface_id IS NOT NULL
           AND CASE scoped.recency_class
               WHEN 1 THEN
                   scoped.source_region_id = scoped.candidate_region_id
               WHEN 2 THEN
                   scoped.source_parent_region_id IS NOT DISTINCT FROM
                       scoped.candidate_parent_region_id
                   AND scoped.candidate_region_end <= scoped.demand_position
               WHEN 3 THEN
                   scoped.source_region_id = scoped.candidate_region_id
                   OR scoped.candidate_region_end <= scoped.demand_position
               WHEN 4 THEN
                   scoped.common_scope_region_kind >= 3
               WHEN 5 THEN
                   scoped.common_scope_region_kind <= 10
               ELSE FALSE
           END
    )
    INSERT INTO execution.semantic_pnf_demand_candidate
        (demand_id, ordinal, target_kind, target_id,
         source_interface_id, ancestor_distance,
         index_rank, candidate_score)
    SELECT valid.demand_id,
           row_number() OVER (
               PARTITION BY valid.demand_id
               ORDER BY valid.candidate_ordinal
           ) - 1,
           valid.target_kind,
           valid.target_id,
           valid.common_scope_interface_id,
           valid.structural_distance,
           valid.index_rank,
           valid.candidate_score
      FROM valid;

    GET DIAGNOSTICS inserted_total = ROW_COUNT;

    WITH updated_demand AS (
        SELECT candidate.demand_id,
               count(*) AS candidate_count
          FROM execution.semantic_pnf_demand_candidate AS candidate
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = candidate.demand_id
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE source_region.run_id = selected_run_id
           AND source_region.document_id = selected_document_id
         GROUP BY candidate.demand_id
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET candidate_count = updated_demand.candidate_count,
           state = CASE
               WHEN updated_demand.candidate_count > 0 THEN 2
               ELSE demand.state
           END
      FROM updated_demand
     WHERE demand.demand_id = updated_demand.demand_id;

    RETURN inserted_total;
END;
$$;

COMMIT;
