BEGIN;

-- C3: feed the certified transported child boundary into the canonical parent
-- reducer.  This migration changes only the source carrier for child exports
-- and child lookups.  Parent-local semantics remain the same: actor-profile
-- compression, salience/promotion, demand candidate ranking, unique-witness
-- discharge, ambiguity preservation, and final authority publication are
-- still owned by rebuild_numeric_pnf_parent_frontier.
--
-- Structural child-interface membership remains a direct region/interface
-- relation because an interface with zero exports can still carry an actor
-- profile.  No token or proposition interior is reconstructed.

CREATE OR REPLACE FUNCTION execution.numeric_pnf_parent_boundary_atoms(
    selected_parent_region_id BIGINT
)
RETURNS TABLE (
    child_region_id BIGINT,
    child_interface_id BIGINT,
    export_kind SMALLINT,
    target_kind SMALLINT,
    target_id BIGINT,
    key_symbol_id BIGINT,
    role_symbol_id BIGINT,
    residual_type_symbol_id BIGINT,
    rank BIGINT,
    promotion_score DOUBLE PRECISION,
    scope_class SMALLINT,
    origin_interface_id BIGINT,
    outward_required BOOLEAN
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT projection.child_region_id,
           projection.child_interface_id,
           projection.export_kind,
           projection.target_kind,
           projection.target_id,
           projection.key_symbol_id,
           projection.role_symbol_id,
           projection.residual_type_symbol_id,
           projection.rank,
           projection.promotion_score,
           projection.scope_class,
           projection.origin_interface_id,
           projection.outward_required
      FROM execution.semantic_pnf_parent_delta_projection AS projection
     WHERE projection.parent_region_id = selected_parent_region_id
     ORDER BY projection.child_interface_id,
              projection.export_kind,
              projection.target_kind,
              projection.target_id
$$;

CREATE OR REPLACE FUNCTION execution.numeric_pnf_parent_lookup_atoms(
    selected_parent_region_id BIGINT
)
RETURNS TABLE (
    child_region_id BIGINT,
    child_interface_id BIGINT,
    key_kind SMALLINT,
    key_a BIGINT,
    key_b BIGINT,
    target_kind SMALLINT,
    target_id BIGINT,
    rank BIGINT
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT projection.child_region_id,
           projection.child_interface_id,
           projection.key_kind,
           projection.key_a,
           projection.key_b,
           projection.target_kind,
           projection.target_id,
           projection.rank
      FROM execution.semantic_pnf_parent_delta_lookup_projection AS projection
     WHERE projection.parent_region_id = selected_parent_region_id
     ORDER BY projection.child_interface_id,
              projection.key_kind,
              projection.key_a,
              projection.key_b,
              projection.target_kind,
              projection.target_id
$$;

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
    selected_region_kind SMALLINT;
    selected_graph_revision BIGINT;
    selected_scope_class SMALLINT;
    threshold_value DOUBLE PRECISION;
    started_at TIMESTAMPTZ := clock_timestamp();
    child_count_value BIGINT := 0;
    input_count_value BIGINT := 0;
    output_count_value BIGINT := 0;
    unresolved_count_value BIGINT := 0;
    resolved_count_value BIGINT := 0;
    actor_count_value BIGINT := 0;
BEGIN
    SELECT interface.region_id,
           region.region_kind,
           interface.graph_revision,
           CASE
               WHEN region.region_kind <= 1 THEN 1
               WHEN region.region_kind <= 2 THEN 2
               WHEN region.region_kind <= 5 THEN 3
               WHEN region.region_kind <= 8 THEN 4
               WHEN region.region_kind = 10 THEN 5
               ELSE 6
           END::SMALLINT,
           profile.promotion_threshold
               + (0.25 * GREATEST(region.region_kind - 1, 0))
      INTO selected_region_id,
           selected_region_kind,
           selected_graph_revision,
           selected_scope_class,
           threshold_value
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
      CROSS JOIN execution.semantic_pnf_mdl_profile AS profile
     WHERE interface.interface_id = selected_interface_id
       AND profile.profile_id = 1;

    IF selected_region_id IS NULL THEN
        RAISE EXCEPTION 'numeric PNF interface % disappeared',
            selected_interface_id;
    END IF;

    IF selected_region_kind = 1 THEN
        SELECT count(*) INTO output_count_value
          FROM execution.semantic_pnf_interface_export
         WHERE interface_id = selected_interface_id;
        SELECT count(*) INTO unresolved_count_value
          FROM execution.semantic_pnf_interface_export AS export
          JOIN execution.semantic_pnf_demand AS demand
            ON export.target_kind = 3
           AND demand.demand_id = export.target_id
         WHERE export.interface_id = selected_interface_id
           AND demand.state IN (1, 3);
        output_export_count := output_count_value;
        unresolved_demand_count := unresolved_count_value;
        resolved_demand_count := 0;
        actor_profile_count := 0;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT count(*) INTO child_count_value
      FROM execution.semantic_pnf_region AS child_region
      JOIN execution.semantic_pnf_interface AS child_interface
        ON child_interface.region_id = child_region.region_id
     WHERE child_region.parent_region_id = selected_region_id
       AND child_region.region_kind <> 9;

    SELECT count(*) INTO input_count_value
      FROM execution.semantic_pnf_parent_delta_projection
     WHERE parent_region_id = selected_region_id;

    DELETE FROM execution.semantic_pnf_interface_lookup
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_interface_export
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_frontier_resolution
     WHERE interface_id = selected_interface_id;

    -- Child actor profiles are already compressed boundary summaries.  Direct
    -- factor participation is read from the transported export boundary.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    ),
    profile_source AS (
        SELECT profile.object_id,
               profile.object_kind_symbol_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               profile.occurrence_count,
               profile.first_start_char,
               profile.last_end_char,
               profile.promotion_score
          FROM child_interface
          JOIN execution.semantic_pnf_actor_profile AS profile
            ON profile.interface_id = child_interface.interface_id
        UNION ALL
        SELECT object.object_id,
               object.object_kind_symbol_id,
               edge.role_symbol_id,
               factor.factor_type_symbol_id,
               factor.predicate_symbol_id,
               1::BIGINT,
               factor_region.start_char,
               factor_region.end_char,
               object.promotion_score
          FROM execution.semantic_pnf_parent_delta_projection AS factor_export
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = factor_export.target_id
          JOIN execution.semantic_pnf_region AS factor_region
            ON factor_region.region_id = factor.region_id
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id = factor.factor_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = edge.object_id
         WHERE factor_export.parent_region_id = selected_region_id
           AND factor_export.target_kind = 2
    )
    INSERT INTO execution.semantic_pnf_actor_profile
        (interface_id, object_id, object_kind_symbol_id,
         role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
         occurrence_count, first_start_char, last_end_char, promotion_score)
    SELECT selected_interface_id,
           source.object_id,
           source.object_kind_symbol_id,
           source.role_symbol_id,
           source.factor_type_symbol_id,
           source.predicate_symbol_id,
           sum(source.occurrence_count),
           min(source.first_start_char),
           max(source.last_end_char),
           max(source.promotion_score)
      FROM profile_source AS source
     GROUP BY source.object_id,
              source.object_kind_symbol_id,
              source.role_symbol_id,
              source.factor_type_symbol_id,
              source.predicate_symbol_id
    ON CONFLICT (
        interface_id, object_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id
    ) DO UPDATE SET
        occurrence_count =
            execution.semantic_pnf_actor_profile.occurrence_count
            + EXCLUDED.occurrence_count,
        first_start_char = LEAST(
            execution.semantic_pnf_actor_profile.first_start_char,
            EXCLUDED.first_start_char
        ),
        last_end_char = GREATEST(
            execution.semantic_pnf_actor_profile.last_end_char,
            EXCLUDED.last_end_char
        ),
        promotion_score = GREATEST(
            execution.semantic_pnf_actor_profile.promotion_score,
            EXCLUDED.promotion_score
        );

    DELETE FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
       AND profile.promotion_score < COALESCE(threshold_value, 0)
       AND profile.occurrence_count < 2
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_parent_delta_projection AS demand_export
             JOIN execution.semantic_pnf_demand AS demand
               ON demand.demand_id = demand_export.target_id
            WHERE demand_export.parent_region_id = selected_region_id
              AND demand_export.target_kind = 3
              AND demand.state IN (1, 3)
              AND demand.expected_target_kind = 1
              AND (
                  demand.expected_object_kind_symbol_id IS NULL
                  OR demand.expected_object_kind_symbol_id
                     = profile.object_kind_symbol_id
              )
              AND (
                  demand.role_symbol_id IS NULL
                  OR demand.role_symbol_id = profile.role_symbol_id
              )
              AND (
                  demand.expected_factor_type_symbol_id IS NULL
                  OR demand.expected_factor_type_symbol_id
                     = profile.factor_type_symbol_id
              )
       );

    -- Unresolved holes cross the boundary from the transported delta carrier.
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT selected_interface_id,
           5,
           3,
           demand.demand_id,
           demand.lexical_symbol_id,
           demand.role_symbol_id,
           demand.residual_type_symbol_id,
           min(child_export.rank),
           0,
           GREATEST(selected_scope_class, max(child_export.scope_class))::SMALLINT,
           min(COALESCE(child_export.origin_interface_id,
                        child_export.child_interface_id)),
           TRUE
      FROM execution.semantic_pnf_parent_delta_projection AS child_export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = child_export.target_id
     WHERE child_export.parent_region_id = selected_region_id
       AND child_export.target_kind = 3
       AND demand.state IN (1, 3)
     GROUP BY demand.demand_id,
              demand.lexical_symbol_id,
              demand.role_symbol_id,
              demand.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    -- Explicit outward declarations are fused directly from transported atoms.
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT selected_interface_id,
           child_export.export_kind,
           child_export.target_kind,
           child_export.target_id,
           child_export.key_symbol_id,
           child_export.role_symbol_id,
           child_export.residual_type_symbol_id,
           min(child_export.rank),
           max(child_export.promotion_score),
           GREATEST(selected_scope_class, max(child_export.scope_class))::SMALLINT,
           min(COALESCE(child_export.origin_interface_id,
                        child_export.child_interface_id)),
           bool_or(child_export.outward_required)
      FROM execution.semantic_pnf_parent_delta_projection AS child_export
     WHERE child_export.parent_region_id = selected_region_id
       AND (
           child_export.target_kind IN (4, 5)
           OR child_export.export_kind IN (3, 4, 6, 7, 8)
       )
     GROUP BY child_export.export_kind,
              child_export.target_kind,
              child_export.target_id,
              child_export.key_symbol_id,
              child_export.role_symbol_id,
              child_export.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    WITH child_object AS (
        SELECT child_export.target_id,
               child_export.key_symbol_id,
               min(child_export.rank) AS rank,
               max(child_export.promotion_score) AS promotion_score,
               count(DISTINCT child_export.child_interface_id) AS child_occurrences,
               min(COALESCE(child_export.origin_interface_id,
                            child_export.child_interface_id)) AS origin_interface_id
          FROM execution.semantic_pnf_parent_delta_projection AS child_export
         WHERE child_export.parent_region_id = selected_region_id
           AND child_export.target_kind = 1
         GROUP BY child_export.target_id, child_export.key_symbol_id
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, rank, promotion_score,
         scope_class, origin_interface_id, outward_required)
    SELECT selected_interface_id,
           1,
           1,
           candidate.target_id,
           candidate.key_symbol_id,
           candidate.rank,
           candidate.promotion_score,
           selected_scope_class,
           candidate.origin_interface_id,
           EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_actor_profile AS profile
                WHERE profile.interface_id = selected_interface_id
                  AND profile.object_id = candidate.target_id
           )
      FROM child_object AS candidate
     WHERE candidate.promotion_score >= COALESCE(threshold_value, 0)
        OR candidate.child_occurrences >= 2
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_actor_profile AS profile
             WHERE profile.interface_id = selected_interface_id
               AND profile.object_id = candidate.target_id
        )
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_demand AS demand
             WHERE demand.state = 2
               AND demand.resolved_target_kind = 1
               AND demand.resolved_target_id = candidate.target_id
        )
    ON CONFLICT DO NOTHING;

    WITH child_factor AS (
        SELECT child_export.target_id,
               child_export.key_symbol_id,
               min(child_export.rank) AS rank,
               min(COALESCE(child_export.origin_interface_id,
                            child_export.child_interface_id)) AS origin_interface_id
          FROM execution.semantic_pnf_parent_delta_projection AS child_export
         WHERE child_export.parent_region_id = selected_region_id
           AND child_export.target_kind = 2
         GROUP BY child_export.target_id, child_export.key_symbol_id
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, rank, promotion_score,
         scope_class, origin_interface_id, outward_required)
    SELECT selected_interface_id,
           2,
           2,
           candidate.target_id,
           candidate.key_symbol_id,
           candidate.rank,
           factor.support_score,
           selected_scope_class,
           candidate.origin_interface_id,
           FALSE
      FROM child_factor AS candidate
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = candidate.target_id
     WHERE factor.support_score >= COALESCE(threshold_value, 0)
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_interface_export AS demand_export
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = demand_export.target_id
             WHERE demand_export.interface_id = selected_interface_id
               AND demand_export.target_kind = 3
               AND demand.expected_target_kind = 2
               AND (
                   demand.expected_factor_type_symbol_id IS NULL
                   OR demand.expected_factor_type_symbol_id
                      = factor.factor_type_symbol_id
               )
               AND (
                   demand.lexical_symbol_id IS NULL
                   OR demand.lexical_symbol_id = factor.predicate_symbol_id
               )
        )
    ON CONFLICT DO NOTHING;

    -- Search projection consumes transported child lookup atoms, then filters
    -- them through the exports actually admitted by parent-local semantics.
    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT selected_interface_id,
           child_lookup.key_kind,
           child_lookup.key_a,
           child_lookup.key_b,
           child_lookup.target_kind,
           child_lookup.target_id,
           min(child_lookup.rank)
      FROM execution.semantic_pnf_parent_delta_lookup_projection AS child_lookup
      JOIN execution.semantic_pnf_interface_export AS parent_export
        ON parent_export.interface_id = selected_interface_id
       AND parent_export.target_kind = child_lookup.target_kind
       AND parent_export.target_id = child_lookup.target_id
     WHERE child_lookup.parent_region_id = selected_region_id
     GROUP BY child_lookup.key_kind,
              child_lookup.key_a,
              child_lookup.key_b,
              child_lookup.target_kind,
              child_lookup.target_id
    ON CONFLICT DO NOTHING;

    -- Everything below is deliberately unchanged parent-local reconciliation.
    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate
     WHERE EXISTS (
         SELECT 1
           FROM execution.semantic_pnf_interface_export AS demand_export
          WHERE demand_export.interface_id = selected_interface_id
            AND demand_export.target_kind = 3
            AND demand_export.target_id = candidate.demand_id
     );

    WITH parent_demand AS (
        SELECT demand.*,
               COALESCE(demand.source_start_char, source_region.end_char)
                   AS demand_position,
               source_region.start_char AS source_region_start,
               source_region.end_char AS source_region_end,
               source_region.parent_region_id AS source_parent_region_id
          FROM execution.semantic_pnf_interface_export AS demand_export
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.state IN (1, 3)
    ),
    object_candidate AS (
        SELECT demand.demand_id,
               1::SMALLINT AS target_kind,
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
           AND (
               demand.expected_object_kind_symbol_id IS NULL
               OR demand.expected_object_kind_symbol_id
                  = profile.object_kind_symbol_id
           )
           AND (
               demand.role_symbol_id IS NULL
               OR demand.role_symbol_id = profile.role_symbol_id
           )
           AND (
               demand.expected_factor_type_symbol_id IS NULL
               OR demand.expected_factor_type_symbol_id
                  = profile.factor_type_symbol_id
           )
           AND (
               demand.lexical_symbol_id IS NULL
               OR demand.lexical_symbol_id = object.head_symbol_id
               OR demand.lexical_symbol_id = profile.predicate_symbol_id
           )
           AND CASE demand.recency_class
               WHEN 1 THEN
                   profile.first_start_char >= demand.source_region_start
                   AND profile.last_end_char <= demand.source_region_end
               WHEN 2 THEN profile.last_end_char <= demand.demand_position
               WHEN 3 THEN profile.last_end_char <= demand.demand_position
               WHEN 4 THEN TRUE
               WHEN 5 THEN TRUE
               ELSE FALSE
           END
    ),
    factor_candidate AS (
        SELECT demand.demand_id,
               2::SMALLINT AS target_kind,
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
           AND (
               demand.expected_factor_type_symbol_id IS NULL
               OR demand.expected_factor_type_symbol_id
                  = factor.factor_type_symbol_id
           )
           AND (
               demand.lexical_symbol_id IS NULL
               OR demand.lexical_symbol_id = factor.predicate_symbol_id
           )
           AND (
               demand.recency_class IN (4, 5)
               OR factor_region.end_char <= demand.demand_position
           )
    ),
    raw_candidate AS (
        SELECT * FROM object_candidate
        UNION ALL
        SELECT * FROM factor_candidate
    ),
    deduplicated AS (
        SELECT candidate.*,
               row_number() OVER (
                   PARTITION BY candidate.demand_id,
                                candidate.target_kind,
                                candidate.target_id
                   ORDER BY candidate.structural_distance,
                            candidate.index_rank,
                            candidate.source_interface_id
               ) AS target_occurrence
          FROM raw_candidate AS candidate
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
    INSERT INTO execution.semantic_pnf_demand_candidate
        (demand_id, ordinal, target_kind, target_id,
         source_interface_id, ancestor_distance,
         index_rank, candidate_score,
         common_scope_interface_id, validation_state)
    SELECT ranked.demand_id,
           ranked.candidate_ordinal::SMALLINT,
           ranked.target_kind,
           ranked.target_id,
           ranked.source_interface_id,
           ranked.structural_distance,
           ranked.index_rank,
           ranked.candidate_score,
           selected_interface_id,
           2
      FROM ranked
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = ranked.demand_id
     WHERE ranked.candidate_ordinal < demand.max_candidates
     ORDER BY ranked.demand_id, ranked.candidate_ordinal
    ON CONFLICT DO NOTHING;

    WITH parent_demand AS (
        SELECT demand.demand_id
          FROM execution.semantic_pnf_interface_export AS demand_export
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.state IN (1, 3)
    ),
    counts AS (
        SELECT parent_demand.demand_id,
               count(candidate.demand_id)::SMALLINT AS candidate_count
          FROM parent_demand
          LEFT JOIN execution.semantic_pnf_demand_candidate AS candidate
            ON candidate.demand_id = parent_demand.demand_id
         GROUP BY parent_demand.demand_id
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET candidate_count = counts.candidate_count,
           state = CASE
               WHEN demand.state = 3 AND counts.candidate_count > 0 THEN 1
               ELSE demand.state
           END
      FROM counts
     WHERE demand.demand_id = counts.demand_id;

    WITH unique_candidate AS (
        SELECT candidate.demand_id,
               min(candidate.target_kind) AS target_kind,
               min(candidate.target_id) AS target_id,
               min(candidate.source_interface_id) AS source_interface_id
          FROM execution.semantic_pnf_demand_candidate AS candidate
          JOIN execution.semantic_pnf_interface_export AS demand_export
            ON demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand_export.target_id = candidate.demand_id
         GROUP BY candidate.demand_id
        HAVING count(*) = 1
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET state = 2,
           resolved_target_kind = unique_candidate.target_kind,
           resolved_target_id = unique_candidate.target_id,
           candidate_count = 1
      FROM unique_candidate
     WHERE demand.demand_id = unique_candidate.demand_id
       AND demand.state IN (1, 3);

    INSERT INTO execution.semantic_pnf_frontier_resolution
        (demand_id, interface_id, outcome_state, candidate_count,
         selected_target_kind, selected_target_id, witness_interface_id)
    SELECT demand.demand_id,
           selected_interface_id,
           CASE
               WHEN demand.state = 2 THEN 2
               WHEN demand.candidate_count = 0
                    AND selected_region_kind = 10 THEN 7
               WHEN demand.candidate_count = 0 THEN 1
               ELSE 3
           END,
           demand.candidate_count,
           demand.resolved_target_kind,
           demand.resolved_target_id,
           CASE WHEN demand.state = 2 THEN selected_interface_id ELSE NULL END
      FROM execution.semantic_pnf_interface_export AS demand_export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = demand_export.target_id
     WHERE demand_export.interface_id = selected_interface_id
       AND demand_export.target_kind = 3
    ON CONFLICT (demand_id, interface_id) DO UPDATE SET
        outcome_state = EXCLUDED.outcome_state,
        candidate_count = EXCLUDED.candidate_count,
        selected_target_kind = EXCLUDED.selected_target_kind,
        selected_target_id = EXCLUDED.selected_target_id,
        witness_interface_id = EXCLUDED.witness_interface_id,
        created_at = CURRENT_TIMESTAMP;

    IF selected_region_kind = 10 THEN
        UPDATE execution.semantic_pnf_demand AS demand
           SET state = 3
          FROM execution.semantic_pnf_interface_export AS demand_export
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.demand_id = demand_export.target_id
           AND demand.state = 1
           AND demand.candidate_count = 0;
    END IF;

    DELETE FROM execution.semantic_pnf_interface_export AS demand_export
    USING execution.semantic_pnf_demand AS demand
     WHERE demand_export.interface_id = selected_interface_id
       AND demand_export.target_kind = 3
       AND demand.demand_id = demand_export.target_id
       AND demand.state = 2;

    DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
     WHERE lookup.interface_id = selected_interface_id
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_interface_export AS export
            WHERE export.interface_id = lookup.interface_id
              AND export.target_kind = lookup.target_kind
              AND export.target_id = lookup.target_id
       );

    SELECT count(*),
           count(*) FILTER (WHERE export.target_kind = 3)
      INTO output_count_value, unresolved_count_value
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id = selected_interface_id;

    SELECT count(*) INTO resolved_count_value
      FROM execution.semantic_pnf_frontier_resolution
     WHERE interface_id = selected_interface_id
       AND outcome_state = 2;

    SELECT count(*) INTO actor_count_value
      FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = selected_interface_id;

    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality = output_count_value,
           promoted_object_count = (
               SELECT count(*)
                 FROM execution.semantic_pnf_interface_export
                WHERE interface_id = selected_interface_id
                  AND target_kind = 1
           ),
           unresolved_count = unresolved_count_value,
           boundary_demand_weight = unresolved_count_value::DOUBLE PRECISION,
           node_count = output_count_value,
           encoded_byte_count = output_count_value * 64,
           interface_digest = digest(
               convert_to(
                   concat_ws(
                       '|',
                       selected_region_id::TEXT,
                       selected_graph_revision::TEXT,
                       output_count_value::TEXT,
                       unresolved_count_value::TEXT,
                       COALESCE((
                           SELECT string_agg(
                               concat_ws(
                                   ':',
                                   export.export_kind::TEXT,
                                   export.target_kind::TEXT,
                                   export.target_id::TEXT,
                                   COALESCE(export.key_symbol_id, 0)::TEXT,
                                   COALESCE(export.role_symbol_id, 0)::TEXT,
                                   COALESCE(export.residual_type_symbol_id, 0)::TEXT
                               ),
                               ',' ORDER BY export.export_kind,
                                            export.target_kind,
                                            export.target_id
                           )
                             FROM execution.semantic_pnf_interface_export AS export
                            WHERE export.interface_id = selected_interface_id
                       ), '')
                   ),
                   'UTF8'
               ),
               'sha256'
           )
     WHERE interface.interface_id = selected_interface_id;

    INSERT INTO execution.semantic_pnf_frontier_reduction_receipt
        (interface_id, graph_revision, child_interface_count,
         input_export_count, output_export_count, actor_profile_count,
         unresolved_demand_count, resolved_demand_count, elapsed_ms)
    VALUES (
        selected_interface_id,
        selected_graph_revision,
        child_count_value,
        input_count_value,
        output_count_value,
        actor_count_value,
        unresolved_count_value,
        resolved_count_value,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        graph_revision = EXCLUDED.graph_revision,
        child_interface_count = EXCLUDED.child_interface_count,
        input_export_count = EXCLUDED.input_export_count,
        output_export_count = EXCLUDED.output_export_count,
        actor_profile_count = EXCLUDED.actor_profile_count,
        unresolved_demand_count = EXCLUDED.unresolved_demand_count,
        resolved_demand_count = EXCLUDED.resolved_demand_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        reduced_at = CURRENT_TIMESTAMP;

    output_export_count := output_count_value;
    unresolved_demand_count := unresolved_count_value;
    resolved_demand_count := resolved_count_value;
    actor_profile_count := actor_count_value;
    RETURN NEXT;
END;
$$;

COMMIT;
