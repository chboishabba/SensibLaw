BEGIN;

-- Close direct child-boundary dirtiness under the dependencies of the parent
-- reducer before counting/touching work.  This is intentionally conservative:
-- an object-side change wakes the open object demands at this parent, and a
-- factor-side change wakes the open factor demands.  It remains fibre-local and
-- never reopens a closed child interior.
CREATE OR REPLACE FUNCTION execution.expand_numeric_pnf_parent_affected_keys(
    selected_parent_region_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    changed BIGINT := 0;
    step_count BIGINT := 0;
BEGIN
    -- Actor summary changes can change concrete-object admission.
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT selected_parent_region_id, 1, key.key_a, 0, 0
      FROM execution.semantic_pnf_parent_affected_key AS key
     WHERE key.parent_region_id = selected_parent_region_id
       AND key.key_family = 4
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS step_count = ROW_COUNT;
    changed := changed + step_count;

    -- A changed factor changes the actor/action summaries of its exposed
    -- participants.  Factor evidence itself remains in the immutable child.
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT DISTINCT selected_parent_region_id,
           4,
           edge.object_id,
           edge.role_symbol_id,
           factor.factor_type_symbol_id
      FROM execution.semantic_pnf_parent_affected_key AS key
      JOIN execution.semantic_pnf_factor AS factor
        ON key.key_family = 2
       AND factor.factor_id = key.key_a
      JOIN execution.semantic_pnf_hyperedge AS edge
        ON edge.factor_id = factor.factor_id
     WHERE key.parent_region_id = selected_parent_region_id
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS step_count = ROW_COUNT;
    changed := changed + step_count;

    -- Newly derived actor keys also imply object admission work.
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT selected_parent_region_id, 1, key.key_a, 0, 0
      FROM execution.semantic_pnf_parent_affected_key AS key
     WHERE key.parent_region_id = selected_parent_region_id
       AND key.key_family = 4
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS step_count = ROW_COUNT;
    changed := changed + step_count;

    -- Any changed object/actor fibre may change any currently exported typed
    -- object demand at this parent.  This is a safe conservative wake-up; the
    -- local candidate reducer still evaluates only those demand IDs.
    IF EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_parent_affected_key
         WHERE parent_region_id = selected_parent_region_id
           AND key_family IN (1, 4)
    ) THEN
        INSERT INTO execution.semantic_pnf_parent_affected_key
            (parent_region_id, key_family, key_a, key_b, key_c)
        SELECT DISTINCT selected_parent_region_id, 3, demand.demand_id, 0, 0
          FROM execution.semantic_pnf_parent_delta_projection AS boundary
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = boundary.target_id
         WHERE boundary.parent_region_id = selected_parent_region_id
           AND boundary.target_kind = 3
           AND demand.state IN (1, 3)
           AND demand.expected_target_kind = 1
        ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS step_count = ROW_COUNT;
        changed := changed + step_count;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_parent_affected_key
         WHERE parent_region_id = selected_parent_region_id
           AND key_family = 2
    ) THEN
        INSERT INTO execution.semantic_pnf_parent_affected_key
            (parent_region_id, key_family, key_a, key_b, key_c)
        SELECT DISTINCT selected_parent_region_id, 3, demand.demand_id, 0, 0
          FROM execution.semantic_pnf_parent_delta_projection AS boundary
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = boundary.target_id
         WHERE boundary.parent_region_id = selected_parent_region_id
           AND boundary.target_kind = 3
           AND demand.state IN (1, 3)
           AND demand.expected_target_kind = 2
        ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS step_count = ROW_COUNT;
        changed := changed + step_count;
    END IF;

    RETURN changed;
END;
$$;

CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_affected(
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
        RAISE EXCEPTION 'numeric PNF interface % disappeared', selected_interface_id;
    END IF;

    SELECT count(DISTINCT child_interface_id), count(*)
      INTO child_count_value, input_count_value
      FROM execution.semantic_pnf_parent_delta_projection
     WHERE parent_region_id = selected_region_id;

    CREATE TEMP TABLE IF NOT EXISTS pg_temp.numeric_pnf_desired_parent_export (
        export_kind SMALLINT NOT NULL,
        target_kind SMALLINT NOT NULL,
        target_id BIGINT NOT NULL,
        key_symbol_id BIGINT,
        role_symbol_id BIGINT,
        residual_type_symbol_id BIGINT,
        rank BIGINT NOT NULL,
        promotion_score DOUBLE PRECISION NOT NULL,
        scope_class SMALLINT NOT NULL,
        origin_interface_id BIGINT,
        outward_required BOOLEAN NOT NULL,
        PRIMARY KEY (export_kind, target_kind, target_id)
    ) ON COMMIT DROP;
    TRUNCATE pg_temp.numeric_pnf_desired_parent_export;

    ------------------------------------------------------------------------
    -- Actor/action summaries: replace only affected actor fibres.
    ------------------------------------------------------------------------
    DELETE FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_parent_affected_key AS key
            WHERE key.parent_region_id = selected_region_id
              AND key.key_family = 4
              AND key.key_a = profile.object_id
              AND key.key_b = COALESCE(profile.role_symbol_id, 0)
              AND key.key_c = COALESCE(profile.factor_type_symbol_id, 0)
       );

    WITH affected_actor AS (
        SELECT key.key_a AS object_id,
               key.key_b AS role_symbol_id,
               key.key_c AS factor_type_symbol_id
          FROM execution.semantic_pnf_parent_affected_key AS key
         WHERE key.parent_region_id = selected_region_id
           AND key.key_family = 4
    ),
    profile_source AS (
        SELECT projection.object_id,
               projection.object_kind_symbol_id,
               projection.role_symbol_id,
               projection.factor_type_symbol_id,
               projection.predicate_symbol_id,
               projection.occurrence_count,
               projection.first_start_char,
               projection.last_end_char,
               projection.promotion_score
          FROM execution.semantic_pnf_parent_actor_delta_projection AS projection
          JOIN affected_actor AS affected
            ON affected.object_id = projection.object_id
           AND affected.role_symbol_id = COALESCE(projection.role_symbol_id, 0)
           AND affected.factor_type_symbol_id =
               COALESCE(projection.factor_type_symbol_id, 0)
         WHERE projection.parent_region_id = selected_region_id
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
          FROM affected_actor AS affected
          JOIN execution.semantic_pnf_parent_delta_projection AS factor_export
            ON factor_export.parent_region_id = selected_region_id
           AND factor_export.target_kind = 2
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = factor_export.target_id
           AND factor.factor_type_symbol_id = affected.factor_type_symbol_id
          JOIN execution.semantic_pnf_region AS factor_region
            ON factor_region.region_id = factor.region_id
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id = factor.factor_id
           AND edge.object_id = affected.object_id
           AND edge.role_symbol_id = affected.role_symbol_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = edge.object_id
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
        object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
        occurrence_count = EXCLUDED.occurrence_count,
        first_start_char = EXCLUDED.first_start_char,
        last_end_char = EXCLUDED.last_end_char,
        promotion_score = EXCLUDED.promotion_score;

    DELETE FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_parent_affected_key AS key
            WHERE key.parent_region_id = selected_region_id
              AND key.key_family = 4
              AND key.key_a = profile.object_id
              AND key.key_b = COALESCE(profile.role_symbol_id, 0)
              AND key.key_c = COALESCE(profile.factor_type_symbol_id, 0)
       )
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
                  OR demand.expected_object_kind_symbol_id = profile.object_kind_symbol_id
              )
              AND (demand.role_symbol_id IS NULL OR demand.role_symbol_id = profile.role_symbol_id)
              AND (
                  demand.expected_factor_type_symbol_id IS NULL
                  OR demand.expected_factor_type_symbol_id = profile.factor_type_symbol_id
              )
       );

    ------------------------------------------------------------------------
    -- Compute desired export rows only for affected fibres.
    ------------------------------------------------------------------------
    WITH child_object AS (
        SELECT boundary.target_id,
               boundary.key_symbol_id,
               min(boundary.rank) AS rank,
               max(boundary.promotion_score) AS promotion_score,
               count(DISTINCT boundary.child_interface_id) AS child_occurrences,
               min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id))
                   AS origin_interface_id
          FROM execution.semantic_pnf_parent_delta_projection AS boundary
          JOIN execution.semantic_pnf_parent_affected_key AS key
            ON key.parent_region_id = selected_region_id
           AND key.key_family = 1
           AND key.key_a = boundary.target_id
         WHERE boundary.parent_region_id = selected_region_id
           AND boundary.target_kind = 1
         GROUP BY boundary.target_id, boundary.key_symbol_id
    )
    INSERT INTO pg_temp.numeric_pnf_desired_parent_export
    SELECT 1, 1,
           candidate.target_id,
           candidate.key_symbol_id,
           NULL, NULL,
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
            SELECT 1 FROM execution.semantic_pnf_actor_profile AS profile
             WHERE profile.interface_id = selected_interface_id
               AND profile.object_id = candidate.target_id
        )
        OR EXISTS (
            SELECT 1 FROM execution.semantic_pnf_demand AS demand
             WHERE demand.state = 2
               AND demand.resolved_target_kind = 1
               AND demand.resolved_target_id = candidate.target_id
        );

    WITH child_factor AS (
        SELECT boundary.target_id,
               boundary.key_symbol_id,
               min(boundary.rank) AS rank,
               min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id))
                   AS origin_interface_id
          FROM execution.semantic_pnf_parent_delta_projection AS boundary
          JOIN execution.semantic_pnf_parent_affected_key AS key
            ON key.parent_region_id = selected_region_id
           AND key.key_family = 2
           AND key.key_a = boundary.target_id
         WHERE boundary.parent_region_id = selected_region_id
           AND boundary.target_kind = 2
         GROUP BY boundary.target_id, boundary.key_symbol_id
    )
    INSERT INTO pg_temp.numeric_pnf_desired_parent_export
    SELECT 2, 2,
           candidate.target_id,
           candidate.key_symbol_id,
           NULL, NULL,
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
              FROM execution.semantic_pnf_parent_delta_projection AS demand_export
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = demand_export.target_id
             WHERE demand_export.parent_region_id = selected_region_id
               AND demand_export.target_kind = 3
               AND demand.state IN (1, 3)
               AND demand.expected_target_kind = 2
               AND (
                   demand.expected_factor_type_symbol_id IS NULL
                   OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id
               )
               AND (
                   demand.lexical_symbol_id IS NULL
                   OR demand.lexical_symbol_id = factor.predicate_symbol_id
               )
        );

    INSERT INTO pg_temp.numeric_pnf_desired_parent_export
    SELECT 5, 3,
           demand.demand_id,
           demand.lexical_symbol_id,
           demand.role_symbol_id,
           demand.residual_type_symbol_id,
           min(boundary.rank),
           0,
           GREATEST(selected_scope_class, max(boundary.scope_class))::SMALLINT,
           min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id)),
           TRUE
      FROM execution.semantic_pnf_parent_delta_projection AS boundary
      JOIN execution.semantic_pnf_parent_affected_key AS key
        ON key.parent_region_id = selected_region_id
       AND key.key_family = 3
       AND key.key_a = boundary.target_id
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = boundary.target_id
     WHERE boundary.parent_region_id = selected_region_id
       AND boundary.target_kind = 3
       AND demand.state IN (1, 3)
     GROUP BY demand.demand_id,
              demand.lexical_symbol_id,
              demand.role_symbol_id,
              demand.residual_type_symbol_id;

    INSERT INTO pg_temp.numeric_pnf_desired_parent_export
    SELECT boundary.export_kind,
           boundary.target_kind,
           boundary.target_id,
           boundary.key_symbol_id,
           boundary.role_symbol_id,
           boundary.residual_type_symbol_id,
           min(boundary.rank),
           max(boundary.promotion_score),
           GREATEST(selected_scope_class, max(boundary.scope_class))::SMALLINT,
           min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id)),
           bool_or(boundary.outward_required)
      FROM execution.semantic_pnf_parent_delta_projection AS boundary
      JOIN execution.semantic_pnf_parent_affected_key AS key
        ON key.parent_region_id = selected_region_id
       AND key.key_family = 5
       AND key.key_a = boundary.export_kind
       AND key.key_b = boundary.target_kind
       AND key.key_c = boundary.target_id
     WHERE boundary.parent_region_id = selected_region_id
     GROUP BY boundary.export_kind,
              boundary.target_kind,
              boundary.target_id,
              boundary.key_symbol_id,
              boundary.role_symbol_id,
              boundary.residual_type_symbol_id;

    -- Delete only affected outputs that are no longer admitted.
    DELETE FROM execution.semantic_pnf_interface_export AS current
     WHERE current.interface_id = selected_interface_id
       AND (
           EXISTS (
               SELECT 1 FROM execution.semantic_pnf_parent_affected_key AS key
                WHERE key.parent_region_id = selected_region_id
                  AND key.key_family = 1
                  AND current.target_kind = 1
                  AND current.target_id = key.key_a
           )
           OR EXISTS (
               SELECT 1 FROM execution.semantic_pnf_parent_affected_key AS key
                WHERE key.parent_region_id = selected_region_id
                  AND key.key_family = 2
                  AND current.target_kind = 2
                  AND current.target_id = key.key_a
           )
           OR EXISTS (
               SELECT 1 FROM execution.semantic_pnf_parent_affected_key AS key
                WHERE key.parent_region_id = selected_region_id
                  AND key.key_family = 3
                  AND current.target_kind = 3
                  AND current.target_id = key.key_a
           )
           OR EXISTS (
               SELECT 1 FROM execution.semantic_pnf_parent_affected_key AS key
                WHERE key.parent_region_id = selected_region_id
                  AND key.key_family = 5
                  AND current.export_kind = key.key_a
                  AND current.target_kind = key.key_b
                  AND current.target_id = key.key_c
           )
       )
       AND NOT EXISTS (
           SELECT 1
             FROM pg_temp.numeric_pnf_desired_parent_export AS desired
            WHERE desired.export_kind = current.export_kind
              AND desired.target_kind = current.target_kind
              AND desired.target_id = current.target_id
       );

    UPDATE execution.semantic_pnf_interface_export AS current
       SET key_symbol_id = desired.key_symbol_id,
           role_symbol_id = desired.role_symbol_id,
           residual_type_symbol_id = desired.residual_type_symbol_id,
           rank = desired.rank,
           promotion_score = desired.promotion_score,
           scope_class = desired.scope_class,
           origin_interface_id = desired.origin_interface_id,
           outward_required = desired.outward_required
      FROM pg_temp.numeric_pnf_desired_parent_export AS desired
     WHERE current.interface_id = selected_interface_id
       AND current.export_kind = desired.export_kind
       AND current.target_kind = desired.target_kind
       AND current.target_id = desired.target_id
       AND ROW(
           current.key_symbol_id,
           current.role_symbol_id,
           current.residual_type_symbol_id,
           current.rank,
           current.promotion_score,
           current.scope_class,
           current.origin_interface_id,
           current.outward_required
       ) IS DISTINCT FROM ROW(
           desired.key_symbol_id,
           desired.role_symbol_id,
           desired.residual_type_symbol_id,
           desired.rank,
           desired.promotion_score,
           desired.scope_class,
           desired.origin_interface_id,
           desired.outward_required
       );

    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT selected_interface_id,
           desired.export_kind,
           desired.target_kind,
           desired.target_id,
           desired.key_symbol_id,
           desired.role_symbol_id,
           desired.residual_type_symbol_id,
           desired.rank,
           desired.promotion_score,
           desired.scope_class,
           desired.origin_interface_id,
           desired.outward_required
      FROM pg_temp.numeric_pnf_desired_parent_export AS desired
    ON CONFLICT (interface_id, export_kind, target_kind, target_id) DO NOTHING;

    ------------------------------------------------------------------------
    -- Candidate/resolution state: only affected demand IDs are reconsidered.
    ------------------------------------------------------------------------
    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate
     WHERE EXISTS (
         SELECT 1
           FROM execution.semantic_pnf_parent_affected_key AS key
          WHERE key.parent_region_id = selected_region_id
            AND key.key_family = 3
            AND key.key_a = candidate.demand_id
     );

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
               OR demand.expected_object_kind_symbol_id = profile.object_kind_symbol_id
           )
           AND (demand.role_symbol_id IS NULL OR demand.role_symbol_id = profile.role_symbol_id)
           AND (
               demand.expected_factor_type_symbol_id IS NULL
               OR demand.expected_factor_type_symbol_id = profile.factor_type_symbol_id
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
               OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id
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

    WITH affected_demand AS (
        SELECT demand.demand_id
          FROM execution.semantic_pnf_parent_affected_key AS key
          JOIN execution.semantic_pnf_interface_export AS demand_export
            ON demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand_export.target_id = key.key_a
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
         WHERE key.parent_region_id = selected_region_id
           AND key.key_family = 3
           AND demand.state IN (1, 3)
    ),
    counts AS (
        SELECT affected_demand.demand_id,
               count(candidate.demand_id)::SMALLINT AS candidate_count
          FROM affected_demand
          LEFT JOIN execution.semantic_pnf_demand_candidate AS candidate
            ON candidate.demand_id = affected_demand.demand_id
         GROUP BY affected_demand.demand_id
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
          JOIN execution.semantic_pnf_parent_affected_key AS key
            ON key.parent_region_id = selected_region_id
           AND key.key_family = 3
           AND key.key_a = candidate.demand_id
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

    DELETE FROM execution.semantic_pnf_frontier_resolution AS resolution
     WHERE resolution.interface_id = selected_interface_id
       AND EXISTS (
           SELECT 1 FROM execution.semantic_pnf_parent_affected_key AS key
            WHERE key.parent_region_id = selected_region_id
              AND key.key_family = 3
              AND key.key_a = resolution.demand_id
       )
       AND NOT EXISTS (
           SELECT 1 FROM execution.semantic_pnf_interface_export AS export
            WHERE export.interface_id = selected_interface_id
              AND export.target_kind = 3
              AND export.target_id = resolution.demand_id
       );

    INSERT INTO execution.semantic_pnf_frontier_resolution
        (demand_id, interface_id, outcome_state, candidate_count,
         selected_target_kind, selected_target_id, witness_interface_id)
    SELECT demand.demand_id,
           selected_interface_id,
           CASE
               WHEN demand.state = 2 THEN 2
               WHEN demand.candidate_count = 0 AND selected_region_kind = 10 THEN 7
               WHEN demand.candidate_count = 0 THEN 1
               ELSE 3
           END,
           demand.candidate_count,
           demand.resolved_target_kind,
           demand.resolved_target_id,
           CASE WHEN demand.state = 2 THEN selected_interface_id ELSE NULL END
      FROM execution.semantic_pnf_parent_affected_key AS key
      JOIN execution.semantic_pnf_interface_export AS demand_export
        ON demand_export.interface_id = selected_interface_id
       AND demand_export.target_kind = 3
       AND demand_export.target_id = key.key_a
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = demand_export.target_id
     WHERE key.parent_region_id = selected_region_id
       AND key.key_family = 3
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
          FROM execution.semantic_pnf_parent_affected_key AS key
          JOIN execution.semantic_pnf_interface_export AS demand_export
            ON demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand_export.target_id = key.key_a
         WHERE key.parent_region_id = selected_region_id
           AND key.key_family = 3
           AND demand.demand_id = demand_export.target_id
           AND demand.state = 1
           AND demand.candidate_count = 0;
    END IF;

    DELETE FROM execution.semantic_pnf_interface_export AS demand_export
    USING execution.semantic_pnf_demand AS demand,
          execution.semantic_pnf_parent_affected_key AS key
     WHERE demand_export.interface_id = selected_interface_id
       AND demand_export.target_kind = 3
       AND demand.demand_id = demand_export.target_id
       AND key.parent_region_id = selected_region_id
       AND key.key_family = 3
       AND key.key_a = demand.demand_id
       AND demand.state = 2;

    ------------------------------------------------------------------------
    -- Lookup is a projection of changed admitted exports only.
    ------------------------------------------------------------------------
    CREATE TEMP TABLE IF NOT EXISTS pg_temp.numeric_pnf_dirty_target (
        target_kind SMALLINT NOT NULL,
        target_id BIGINT NOT NULL,
        PRIMARY KEY (target_kind, target_id)
    ) ON COMMIT DROP;
    TRUNCATE pg_temp.numeric_pnf_dirty_target;

    INSERT INTO pg_temp.numeric_pnf_dirty_target
    SELECT key.key_family, key.key_a
      FROM execution.semantic_pnf_parent_affected_key AS key
     WHERE key.parent_region_id = selected_region_id
       AND key.key_family IN (1, 2, 3)
    ON CONFLICT DO NOTHING;
    INSERT INTO pg_temp.numeric_pnf_dirty_target
    SELECT key.key_b::SMALLINT, key.key_c
      FROM execution.semantic_pnf_parent_affected_key AS key
     WHERE key.parent_region_id = selected_region_id
       AND key.key_family = 5
    ON CONFLICT DO NOTHING;

    DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
     WHERE lookup.interface_id = selected_interface_id
       AND EXISTS (
           SELECT 1 FROM pg_temp.numeric_pnf_dirty_target AS dirty
            WHERE dirty.target_kind = lookup.target_kind
              AND dirty.target_id = lookup.target_id
       );

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT selected_interface_id, 3, export.key_symbol_id, 0,
           export.target_kind, export.target_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 1
       AND export.key_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 1, factor.factor_type_symbol_id, 0,
           2, factor.factor_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 2
    UNION ALL
    SELECT selected_interface_id, 3, factor.predicate_symbol_id, 0,
           2, factor.factor_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 2
    UNION ALL
    SELECT selected_interface_id, 5, demand.residual_type_symbol_id,
           COALESCE(demand.expected_factor_type_symbol_id, 0),
           3, demand.demand_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 3
       AND demand.residual_type_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 3, demand.lexical_symbol_id,
           COALESCE(demand.residual_type_symbol_id, 0),
           3, demand.demand_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 3
       AND demand.lexical_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 6, export.key_symbol_id, 0,
           export.target_kind, export.target_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 4
       AND export.key_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 7, export.key_symbol_id, 0,
           export.target_kind, export.target_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN pg_temp.numeric_pnf_dirty_target AS dirty
        ON dirty.target_kind = export.target_kind
       AND dirty.target_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 5
       AND export.key_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    ------------------------------------------------------------------------
    -- Bounded parent publication summary.  The output frontier itself is under
    -- the explicit exact-key budget; this scan is publication, not reopening
    -- accumulated child state.
    ------------------------------------------------------------------------
    SELECT count(*), count(*) FILTER (WHERE target_kind = 3)
      INTO output_count_value, unresolved_count_value
      FROM execution.semantic_pnf_interface_export
     WHERE interface_id = selected_interface_id;
    SELECT count(*) INTO resolved_count_value
      FROM execution.semantic_pnf_frontier_resolution
     WHERE interface_id = selected_interface_id AND outcome_state = 2;
    SELECT count(*) INTO actor_count_value
      FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = selected_interface_id;

    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality = output_count_value,
           promoted_object_count = (
               SELECT count(*) FROM execution.semantic_pnf_interface_export
                WHERE interface_id = selected_interface_id AND target_kind = 1
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
                                   ':', export.export_kind::TEXT,
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
        0
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        graph_revision = EXCLUDED.graph_revision,
        child_interface_count = EXCLUDED.child_interface_count,
        input_export_count = EXCLUDED.input_export_count,
        output_export_count = EXCLUDED.output_export_count,
        actor_profile_count = EXCLUDED.actor_profile_count,
        unresolved_demand_count = EXCLUDED.unresolved_demand_count,
        resolved_demand_count = EXCLUDED.resolved_demand_count,
        reduced_at = CURRENT_TIMESTAMP;

    output_export_count := output_count_value;
    unresolved_demand_count := unresolved_count_value;
    resolved_demand_count := resolved_count_value;
    actor_profile_count := actor_count_value;
    RETURN NEXT;
END;
$$;

-- Activate key-local warm reduction.  Cold construction still uses the complete
-- transported-boundary oracle; warm dirty calls reduce only the dependency-
-- closed affected key set.  Zero-dirty warm calls remain true no-ops.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_delta_native(
    selected_interface_id BIGINT,
    selected_hierarchy_depth BIGINT,
    selected_key_budget BIGINT
)
RETURNS TABLE (
    parent_region_id BIGINT,
    input_delta_atoms BIGINT,
    accumulated_boundary_keys BIGINT,
    touched_boundary_keys BIGINT,
    object_keys_touched BIGINT,
    factor_keys_touched BIGINT,
    demand_keys_touched BIGINT,
    actor_keys_touched BIGINT,
    outward_keys_touched BIGINT,
    emitted_parent_deltas BIGINT,
    hierarchy_depth BIGINT,
    cold_build BOOLEAN,
    output_export_count BIGINT,
    unresolved_demand_count BIGINT,
    resolved_demand_count BIGINT,
    actor_profile_count BIGINT,
    elapsed_ms DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region_id BIGINT;
    started_at TIMESTAMPTZ := clock_timestamp();
    cold_value BOOLEAN;
    input_atoms BIGINT;
    accumulated_keys BIGINT;
    accumulated_object_keys BIGINT;
    accumulated_factor_keys BIGINT;
    accumulated_demand_keys BIGINT;
    touched BIGINT;
    object_keys BIGINT;
    factor_keys BIGINT;
    demand_keys BIGINT;
    actor_keys BIGINT;
    outward_keys BIGINT;
    output_value BIGINT;
    unresolved_value BIGINT;
    resolved_value BIGINT;
    actor_value BIGINT;
    emitted_value BIGINT := 0;
BEGIN
    IF selected_hierarchy_depth < 0 OR selected_key_budget < 1 THEN
        RAISE EXCEPTION 'invalid delta-native hierarchy depth/key budget';
    END IF;

    SELECT region_id INTO selected_region_id
      FROM execution.semantic_pnf_interface
     WHERE interface_id = selected_interface_id;
    IF selected_region_id IS NULL THEN
        RAISE EXCEPTION 'numeric PNF interface % disappeared', selected_interface_id;
    END IF;

    cold_value := NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_frontier_reduction_receipt
         WHERE interface_id = selected_interface_id
    );

    IF NOT cold_value THEN
        PERFORM execution.expand_numeric_pnf_parent_affected_keys(selected_region_id);
    END IF;

    SELECT
        (SELECT count(*)
           FROM execution.semantic_pnf_parent_delta_projection AS projection
          WHERE projection.parent_region_id = selected_region_id)
        +
        (SELECT count(*)
           FROM execution.semantic_pnf_parent_actor_delta_projection AS actor
          WHERE actor.parent_region_id = selected_region_id)
      INTO input_atoms;

    SELECT count(*),
           count(*) FILTER (WHERE family = 1),
           count(*) FILTER (WHERE family = 2),
           count(*) FILTER (WHERE family = 3)
      INTO accumulated_keys,
           accumulated_object_keys,
           accumulated_factor_keys,
           accumulated_demand_keys
      FROM (
          SELECT 1::SMALLINT AS family, target_id AS a, 0::BIGINT AS b, 0::BIGINT AS c
            FROM execution.semantic_pnf_parent_delta_projection AS projection
           WHERE projection.parent_region_id = selected_region_id
             AND projection.target_kind = 1
          UNION
          SELECT 2, target_id, 0, 0
            FROM execution.semantic_pnf_parent_delta_projection AS projection
           WHERE projection.parent_region_id = selected_region_id
             AND projection.target_kind = 2
          UNION
          SELECT 3, target_id, 0, 0
            FROM execution.semantic_pnf_parent_delta_projection AS projection
           WHERE projection.parent_region_id = selected_region_id
             AND projection.target_kind = 3
          UNION
          SELECT 4, object_id, COALESCE(role_symbol_id, 0),
                 COALESCE(factor_type_symbol_id, 0)
            FROM execution.semantic_pnf_parent_actor_delta_projection AS actor
           WHERE actor.parent_region_id = selected_region_id
          UNION
          SELECT 5, export_kind, target_kind, target_id
            FROM execution.semantic_pnf_parent_delta_projection AS projection
           WHERE projection.parent_region_id = selected_region_id
             AND projection.target_kind NOT IN (1, 2, 3)
      ) AS keys(family, a, b, c);

    IF GREATEST(
        accumulated_object_keys,
        accumulated_factor_keys,
        accumulated_demand_keys
    ) > selected_key_budget THEN
        RAISE EXCEPTION
            'delta-native parent % exceeds accumulated exact key budget % '
            '(object %, factor %, demand %)',
            selected_region_id,
            selected_key_budget,
            accumulated_object_keys,
            accumulated_factor_keys,
            accumulated_demand_keys;
    END IF;

    SELECT count(*),
           count(*) FILTER (WHERE key_family = 1),
           count(*) FILTER (WHERE key_family = 2),
           count(*) FILTER (WHERE key_family = 3),
           count(*) FILTER (WHERE key_family = 4),
           count(*) FILTER (WHERE key_family = 5)
      INTO touched, object_keys, factor_keys, demand_keys, actor_keys, outward_keys
      FROM execution.semantic_pnf_parent_affected_key AS key
     WHERE key.parent_region_id = selected_region_id;

    IF GREATEST(object_keys, factor_keys, demand_keys, actor_keys, outward_keys)
       > selected_key_budget THEN
        RAISE EXCEPTION
            'delta-native parent % exceeds touched per-family key budget %',
            selected_region_id, selected_key_budget;
    END IF;

    IF NOT cold_value AND touched = 0 THEN
        SELECT interface_cardinality, unresolved_count
          INTO output_value, unresolved_value
          FROM execution.semantic_pnf_interface
         WHERE interface_id = selected_interface_id;
        SELECT count(*) INTO resolved_value
          FROM execution.semantic_pnf_frontier_resolution
         WHERE interface_id = selected_interface_id AND outcome_state = 2;
        SELECT count(*) INTO actor_value
          FROM execution.semantic_pnf_actor_profile
         WHERE interface_id = selected_interface_id;
        emitted_value := 0;
    ELSE
        IF cold_value THEN
            SELECT result.output_export_count,
                   result.unresolved_demand_count,
                   result.resolved_demand_count,
                   result.actor_profile_count
              INTO output_value, unresolved_value, resolved_value, actor_value
              FROM execution.rebuild_numeric_pnf_parent_frontier_delta_input(
                  selected_interface_id
              ) AS result;
        ELSE
            SELECT result.output_export_count,
                   result.unresolved_demand_count,
                   result.resolved_demand_count,
                   result.actor_profile_count
              INTO output_value, unresolved_value, resolved_value, actor_value
              FROM execution.reduce_numeric_pnf_parent_frontier_affected(
                  selected_interface_id
              ) AS result;
        END IF;

        emitted_value := execution.refresh_numeric_pnf_parent_output_fingerprints(
            selected_interface_id
        );
        DELETE FROM execution.semantic_pnf_parent_affected_key AS key
         WHERE key.parent_region_id = selected_region_id;
    END IF;

    INSERT INTO execution.semantic_pnf_delta_native_parent_work_receipt
        (interface_id, parent_region_id, input_delta_atoms,
         accumulated_boundary_keys, touched_boundary_keys,
         object_keys_touched, factor_keys_touched, demand_keys_touched,
         actor_keys_touched, outward_keys_touched,
         emitted_parent_deltas, hierarchy_depth, cold_build,
         output_export_count, unresolved_demand_count,
         resolved_demand_count, actor_profile_count, elapsed_ms)
    VALUES (
        selected_interface_id, selected_region_id, input_atoms,
        accumulated_keys, touched,
        object_keys, factor_keys, demand_keys, actor_keys, outward_keys,
        emitted_value, selected_hierarchy_depth, cold_value,
        output_value, unresolved_value, resolved_value, actor_value,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        parent_region_id = EXCLUDED.parent_region_id,
        input_delta_atoms = EXCLUDED.input_delta_atoms,
        accumulated_boundary_keys = EXCLUDED.accumulated_boundary_keys,
        touched_boundary_keys = EXCLUDED.touched_boundary_keys,
        object_keys_touched = EXCLUDED.object_keys_touched,
        factor_keys_touched = EXCLUDED.factor_keys_touched,
        demand_keys_touched = EXCLUDED.demand_keys_touched,
        actor_keys_touched = EXCLUDED.actor_keys_touched,
        outward_keys_touched = EXCLUDED.outward_keys_touched,
        emitted_parent_deltas = EXCLUDED.emitted_parent_deltas,
        hierarchy_depth = EXCLUDED.hierarchy_depth,
        cold_build = EXCLUDED.cold_build,
        output_export_count = EXCLUDED.output_export_count,
        unresolved_demand_count = EXCLUDED.unresolved_demand_count,
        resolved_demand_count = EXCLUDED.resolved_demand_count,
        actor_profile_count = EXCLUDED.actor_profile_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        reduced_at = CURRENT_TIMESTAMP;

    RETURN QUERY
    SELECT selected_region_id,
           input_atoms,
           accumulated_keys,
           touched,
           object_keys,
           factor_keys,
           demand_keys,
           actor_keys,
           outward_keys,
           emitted_value,
           selected_hierarchy_depth,
           cold_value,
           output_value,
           unresolved_value,
           resolved_value,
           actor_value,
           EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000;
END;
$$;

COMMENT ON FUNCTION execution.reduce_numeric_pnf_parent_frontier_affected(BIGINT) IS
    'Warm C3b reducer: dependency-close the dirty parent key set, recompute only affected actor/export/demand/lookup fibres, and leave all unrelated parent state untouched.';

COMMIT;
