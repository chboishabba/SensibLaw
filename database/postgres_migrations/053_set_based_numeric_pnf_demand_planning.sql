BEGIN;

-- Normalize the heterogeneous demand predicate once. Candidate planning can
-- then use the numeric global-lookup B-tree without a large OR expression or a
-- procedural loop per demand.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_lookup_key (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    key_kind SMALLINT NOT NULL CHECK (key_kind BETWEEN 1 AND 7),
    key_a BIGINT NOT NULL,
    key_b BIGINT NOT NULL DEFAULT 0,
    target_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_target_kind(kind_id)
        ON DELETE RESTRICT,
    PRIMARY KEY (demand_id, key_kind, key_a, key_b, target_kind)
);

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_lookup_key_join_idx
    ON execution.semantic_pnf_demand_lookup_key
       (key_kind, key_a, key_b, target_kind, demand_id);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_demand_lookup_keys()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_demand_lookup_key
     WHERE demand_id = NEW.demand_id;

    INSERT INTO execution.semantic_pnf_demand_lookup_key
        (demand_id, key_kind, key_a, key_b, target_kind)
    SELECT NEW.demand_id, key_kind, key_a, key_b, NEW.expected_target_kind
      FROM (
          SELECT 1::SMALLINT AS key_kind,
                 NEW.expected_factor_type_symbol_id AS key_a,
                 0::BIGINT AS key_b
           WHERE NEW.expected_factor_type_symbol_id IS NOT NULL
          UNION ALL
          SELECT 2::SMALLINT,
                 NEW.expected_object_kind_symbol_id,
                 0::BIGINT
           WHERE NEW.expected_object_kind_symbol_id IS NOT NULL
          UNION ALL
          SELECT 3::SMALLINT,
                 NEW.lexical_symbol_id,
                 0::BIGINT
           WHERE NEW.lexical_symbol_id IS NOT NULL
          UNION ALL
          SELECT 5::SMALLINT,
                 NEW.residual_type_symbol_id,
                 0::BIGINT
           WHERE NEW.residual_type_symbol_id IS NOT NULL
      ) AS key_rows
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_lookup_keys
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_lookup_keys
AFTER INSERT OR UPDATE OF
    expected_target_kind,
    expected_factor_type_symbol_id,
    expected_object_kind_symbol_id,
    lexical_symbol_id,
    residual_type_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.refresh_numeric_pnf_demand_lookup_keys();

-- Backfill pre-existing demands on an upgraded database.
INSERT INTO execution.semantic_pnf_demand_lookup_key
    (demand_id, key_kind, key_a, key_b, target_kind)
SELECT demand.demand_id,
       key_rows.key_kind,
       key_rows.key_a,
       0,
       demand.expected_target_kind
  FROM execution.semantic_pnf_demand AS demand
  CROSS JOIN LATERAL (
      SELECT 1::SMALLINT, demand.expected_factor_type_symbol_id
       WHERE demand.expected_factor_type_symbol_id IS NOT NULL
      UNION ALL
      SELECT 2::SMALLINT, demand.expected_object_kind_symbol_id
       WHERE demand.expected_object_kind_symbol_id IS NOT NULL
      UNION ALL
      SELECT 3::SMALLINT, demand.lexical_symbol_id
       WHERE demand.lexical_symbol_id IS NOT NULL
      UNION ALL
      SELECT 5::SMALLINT, demand.residual_type_symbol_id
       WHERE demand.residual_type_symbol_id IS NOT NULL
  ) AS key_rows(key_kind, key_a)
ON CONFLICT DO NOTHING;

-- Candidate visibility is now evaluated in the set-based planner. Remove the
-- recursive per-row trigger; retain the historical function only for migration
-- compatibility and forensic comparison.
DROP TRIGGER IF EXISTS semantic_pnf_demand_candidate_visibility
    ON execution.semantic_pnf_demand_candidate;

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
               object.promotion_score AS candidate_score,
               global.region_end_char - global.region_start_char
                   AS export_scope_width
          FROM selected_demand AS demand
          JOIN execution.semantic_pnf_global_lookup AS global
            ON global.run_id = selected_run_id
           AND global.document_id = selected_document_id
           AND global.target_kind = 1
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = global.target_id
          JOIN execution.semantic_pnf_region AS origin_region
            ON origin_region.region_id = object.region_id
          LEFT JOIN execution.semantic_pnf_interface AS origin_interface
            ON origin_interface.region_id = origin_region.region_id
         WHERE demand.residual_type_symbol_id = anaphor_residual_id
           AND origin_region.region_id <> demand.source_region_id
           AND origin_region.end_char <= demand.demand_position
           AND (
               pronoun_kind_id IS NULL
               OR object.object_kind_symbol_id <> pronoun_kind_id
           )
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
    scoped AS (
        SELECT bounded.*,
               common_scope.interface_id AS common_scope_interface_id,
               common_scope.region_kind AS common_scope_region_kind
          FROM bounded
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
         WHERE bounded.candidate_ordinal < bounded.max_candidates
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
         index_rank, candidate_score,
         common_scope_interface_id, validation_state)
    SELECT valid.demand_id,
           valid.candidate_ordinal::SMALLINT,
           valid.target_kind,
           valid.target_id,
           valid.candidate_interface_id,
           valid.structural_distance,
           valid.index_rank,
           valid.candidate_score,
           valid.common_scope_interface_id,
           2
      FROM valid
     ORDER BY valid.demand_id, valid.candidate_ordinal
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS inserted_total = ROW_COUNT;

    WITH selected_demand AS (
        SELECT demand.demand_id
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE source_region.run_id = selected_run_id
           AND source_region.document_id = selected_document_id
           AND demand.state IN (1, 2)
    ),
    candidate_count AS (
        SELECT selected.demand_id,
               count(candidate.demand_id)::SMALLINT AS candidate_count
          FROM selected_demand AS selected
          LEFT JOIN execution.semantic_pnf_demand_candidate AS candidate
            ON candidate.demand_id = selected.demand_id
         GROUP BY selected.demand_id
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET candidate_count = counts.candidate_count,
           state = CASE
               WHEN counts.candidate_count > 0 THEN 2
               ELSE demand.state
           END
      FROM candidate_count AS counts
     WHERE demand.demand_id = counts.demand_id;

    UPDATE execution.semantic_pnf_demand AS demand
       SET state = 3
      FROM execution.semantic_pnf_region AS source_region
     WHERE source_region.region_id = demand.source_region_id
       AND source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id
       AND demand.state = 1
       AND demand.candidate_count = 0
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_region AS document_region
            WHERE document_region.run_id = selected_run_id
              AND document_region.document_id = selected_document_id
              AND document_region.region_kind = 10
              AND document_region.closure_state = 3
       );

    RETURN inserted_total;
END;
$$;

COMMIT;
