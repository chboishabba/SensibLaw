BEGIN;

-- 178: a sparse retained frontier does not imply sparse transition work.
-- Migration 062 correctly retained only a compressed parent boundary, but its
-- object_candidate CTE joined every unresolved object demand to every actor
-- profile in that parent and filtered the Cartesian product afterwards.  The
-- adaptive-block probe exposed this physical mismatch directly: a bounded
-- parent fibre with 11k+ unresolved demands drove hundreds of seconds of
-- PL/pgSQL/SPI work and massive temp spill.
--
-- Preserve the candidate relation exactly while changing only exposure:
--   demand -> required typed key fibre
--   actor profile -> available typed key fibre
--   indexed key intersection -> profile iff all required keys matched
--   zero-key demand -> explicit broad fallback
--   recency/scoring/dedup/ranking -> unchanged downstream semantics
--
-- The existing semantic_pnf_demand_constraint relation remains the persisted
-- typed-key authority.  Before using it, the helper fails closed unless its
-- object-candidate keys exactly match the canonical demand columns consumed by
-- migration 062.  No missing/stale constraint row may silently prune authority.

CREATE OR REPLACE FUNCTION execution.indexed_numeric_pnf_object_candidate_rows(
    selected_interface_id BIGINT
)
RETURNS TABLE (
    demand_id BIGINT,
    target_kind SMALLINT,
    target_id BIGINT,
    source_interface_id BIGINT,
    structural_distance BIGINT,
    index_rank BIGINT,
    candidate_score DOUBLE PRECISION
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    -- Mechanical parity boundary: migration 062's historical object-candidate
    -- semantics are the four nullable demand columns below.  The persisted
    -- constraint fibre may drive execution only when it represents exactly the
    -- same positive required keys for the parent object demands.
    IF EXISTS (
        WITH parent_demand AS MATERIALIZED (
            SELECT demand.demand_id,
                   demand.expected_factor_type_symbol_id,
                   demand.expected_object_kind_symbol_id,
                   demand.lexical_symbol_id,
                   demand.role_symbol_id
              FROM execution.semantic_pnf_interface_export AS demand_export
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = demand_export.target_id
             WHERE demand_export.interface_id = selected_interface_id
               AND demand_export.target_kind = 3
               AND demand.state IN (1, 3)
               AND demand.expected_target_kind = 1
        ),
        expected_key AS (
            SELECT parent_demand.demand_id,
                   1::SMALLINT AS key_kind,
                   parent_demand.expected_factor_type_symbol_id AS key_a,
                   0::BIGINT AS key_b
              FROM parent_demand
             WHERE parent_demand.expected_factor_type_symbol_id IS NOT NULL
            UNION ALL
            SELECT parent_demand.demand_id,
                   2::SMALLINT,
                   parent_demand.expected_object_kind_symbol_id,
                   0::BIGINT
              FROM parent_demand
             WHERE parent_demand.expected_object_kind_symbol_id IS NOT NULL
            UNION ALL
            SELECT parent_demand.demand_id,
                   3::SMALLINT,
                   parent_demand.lexical_symbol_id,
                   0::BIGINT
              FROM parent_demand
             WHERE parent_demand.lexical_symbol_id IS NOT NULL
            UNION ALL
            SELECT parent_demand.demand_id,
                   4::SMALLINT,
                   parent_demand.role_symbol_id,
                   0::BIGINT
              FROM parent_demand
             WHERE parent_demand.role_symbol_id IS NOT NULL
        ),
        actual_key AS (
            SELECT constraint_row.demand_id,
                   constraint_row.key_kind,
                   constraint_row.key_a,
                   constraint_row.key_b
              FROM parent_demand AS demand
              JOIN execution.semantic_pnf_demand_constraint AS constraint_row
                ON constraint_row.demand_id = demand.demand_id
             WHERE constraint_row.required
               AND constraint_row.polarity = 1
               AND constraint_row.key_kind IN (1, 2, 3, 4)
        ),
        difference AS (
            (SELECT * FROM expected_key EXCEPT SELECT * FROM actual_key)
            UNION ALL
            (SELECT * FROM actual_key EXCEPT SELECT * FROM expected_key)
        )
        SELECT 1 FROM difference LIMIT 1
    ) THEN
        RAISE EXCEPTION
            'numeric PNF object-demand constraint fibre disagrees with canonical demand columns for interface %',
            selected_interface_id;
    END IF;

    RETURN QUERY
    WITH parent_demand AS MATERIALIZED (
        SELECT demand.demand_id,
               demand.expected_target_kind,
               COALESCE(demand.source_start_char, source_region.end_char)
                   AS demand_position,
               source_region.start_char AS source_region_start,
               source_region.end_char AS source_region_end,
               demand.recency_class
          FROM execution.semantic_pnf_interface_export AS demand_export
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.state IN (1, 3)
           AND demand.expected_target_kind = 1
    ),
    required_key AS MATERIALIZED (
        SELECT constraint_row.demand_id,
               constraint_row.key_kind,
               constraint_row.key_a,
               constraint_row.key_b
          FROM parent_demand AS demand
          JOIN execution.semantic_pnf_demand_constraint AS constraint_row
            ON constraint_row.demand_id = demand.demand_id
         WHERE constraint_row.required
           AND constraint_row.polarity = 1
           AND constraint_row.key_kind IN (1, 2, 3, 4)
    ),
    required_count AS MATERIALIZED (
        SELECT required_key.demand_id,
               count(*)::BIGINT AS required_count
          FROM required_key
         GROUP BY required_key.demand_id
    ),
    profile_base AS MATERIALIZED (
        SELECT profile.object_id,
               profile.object_kind_symbol_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               profile.occurrence_count,
               profile.first_start_char,
               profile.last_end_char,
               profile.promotion_score,
               object.head_symbol_id
          FROM execution.semantic_pnf_actor_profile AS profile
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = profile.object_id
         WHERE profile.interface_id = selected_interface_id
    ),
    profile_key AS MATERIALIZED (
        SELECT DISTINCT
               profile.object_id,
               profile.object_kind_symbol_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               profile.occurrence_count,
               profile.first_start_char,
               profile.last_end_char,
               profile.promotion_score,
               key.key_kind,
               key.key_a,
               0::BIGINT AS key_b
          FROM profile_base AS profile
          CROSS JOIN LATERAL (
              VALUES
                  (1::SMALLINT, profile.factor_type_symbol_id),
                  (2::SMALLINT, profile.object_kind_symbol_id),
                  (3::SMALLINT, profile.predicate_symbol_id),
                  (3::SMALLINT, profile.head_symbol_id),
                  (4::SMALLINT, profile.role_symbol_id)
          ) AS key(key_kind, key_a)
         WHERE key.key_a IS NOT NULL
    ),
    matched_profile AS MATERIALIZED (
        SELECT required_key.demand_id,
               profile.object_id,
               profile.object_kind_symbol_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               profile.occurrence_count,
               profile.first_start_char,
               profile.last_end_char,
               profile.promotion_score,
               count(*)::BIGINT AS matched_count
          FROM required_key
          JOIN profile_key AS profile
            ON profile.key_kind = required_key.key_kind
           AND profile.key_a = required_key.key_a
           AND profile.key_b = required_key.key_b
         GROUP BY required_key.demand_id,
                  profile.object_id,
                  profile.object_kind_symbol_id,
                  profile.role_symbol_id,
                  profile.factor_type_symbol_id,
                  profile.predicate_symbol_id,
                  profile.occurrence_count,
                  profile.first_start_char,
                  profile.last_end_char,
                  profile.promotion_score
    ),
    indexed_profile AS (
        SELECT matched.demand_id,
               matched.object_id,
               matched.occurrence_count,
               matched.first_start_char,
               matched.last_end_char,
               matched.promotion_score
          FROM matched_profile AS matched
          JOIN required_count AS required
            ON required.demand_id = matched.demand_id
           AND required.required_count = matched.matched_count
    ),
    broad_profile AS (
        -- Absence of object-candidate constraints is not negative evidence.
        -- Preserve migration 062's wildcard semantics explicitly.
        SELECT demand.demand_id,
               profile.object_id,
               profile.occurrence_count,
               profile.first_start_char,
               profile.last_end_char,
               profile.promotion_score
          FROM parent_demand AS demand
          LEFT JOIN required_count AS required
            ON required.demand_id = demand.demand_id
          CROSS JOIN profile_base AS profile
         WHERE required.demand_id IS NULL
    ),
    candidate_profile AS (
        SELECT * FROM indexed_profile
        UNION ALL
        SELECT * FROM broad_profile
    )
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
      FROM candidate_profile AS profile
      JOIN parent_demand AS demand
        ON demand.demand_id = profile.demand_id
     WHERE CASE demand.recency_class
         WHEN 1 THEN
             profile.first_start_char >= demand.source_region_start
             AND profile.last_end_char <= demand.source_region_end
         WHEN 2 THEN
             profile.last_end_char <= demand.demand_position
         WHEN 3 THEN
             profile.last_end_char <= demand.demand_position
         WHEN 4 THEN TRUE
         WHEN 5 THEN TRUE
         ELSE FALSE
     END;
END;
$$;

-- Replace only migration 062's object_candidate CTE.  Keeping the rest of the
-- canonical reducer byte-for-byte at runtime avoids creating a second frontier
-- authority.  The patch is intentionally fail-closed: if a later migration has
-- already changed the expected Cartesian candidate block, installation aborts
-- rather than applying an unreviewed textual rewrite.
DO $migration$
DECLARE
    source_body TEXT;
    patched_body TEXT;
    object_start INTEGER;
    factor_start INTEGER;
    old_object_block TEXT;
    replacement TEXT := E'    object_candidate AS (\n'
        || E'        SELECT candidate.demand_id,\n'
        || E'               candidate.target_kind,\n'
        || E'               candidate.target_id,\n'
        || E'               candidate.source_interface_id,\n'
        || E'               candidate.structural_distance,\n'
        || E'               candidate.index_rank,\n'
        || E'               candidate.candidate_score\n'
        || E'          FROM execution.indexed_numeric_pnf_object_candidate_rows(\n'
        || E'              selected_interface_id\n'
        || E'          ) AS candidate\n'
        || E'    ),\n';
BEGIN
    SELECT procedure.prosrc
      INTO source_body
      FROM pg_proc AS procedure
      JOIN pg_namespace AS namespace
        ON namespace.oid = procedure.pronamespace
     WHERE namespace.nspname = 'execution'
       AND procedure.proname = 'rebuild_numeric_pnf_parent_frontier'
       AND procedure.pronargs = 1
       AND procedure.proargtypes[0] = 'int8'::regtype::oid;

    IF source_body IS NULL THEN
        RAISE EXCEPTION
            'migration 178 cannot find execution.rebuild_numeric_pnf_parent_frontier(bigint)';
    END IF;

    IF strpos(
        source_body,
        'execution.indexed_numeric_pnf_object_candidate_rows('
    ) > 0 THEN
        RETURN;
    END IF;

    object_start := strpos(source_body, E'    object_candidate AS (\n');
    factor_start := strpos(source_body, E'    factor_candidate AS (\n');
    IF object_start = 0 OR factor_start = 0 OR factor_start <= object_start THEN
        RAISE EXCEPTION
            'migration 178 cannot locate the canonical object/factor candidate CTE boundary';
    END IF;

    old_object_block := substr(
        source_body,
        object_start,
        factor_start - object_start
    );
    IF strpos(
        old_object_block,
        'JOIN execution.semantic_pnf_actor_profile AS profile'
    ) = 0
       OR strpos(
           old_object_block,
           'demand.expected_object_kind_symbol_id IS NULL'
       ) = 0
       OR strpos(
           old_object_block,
           'demand.lexical_symbol_id = object.head_symbol_id'
       ) = 0
       OR strpos(
           old_object_block,
           'demand.lexical_symbol_id = profile.predicate_symbol_id'
       ) = 0 THEN
        RAISE EXCEPTION
            'migration 178 refuses to replace an unrecognised object-candidate implementation';
    END IF;

    patched_body := substr(source_body, 1, object_start - 1)
        || replacement
        || substr(source_body, factor_start);

    EXECUTE
        'CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier('
        || 'selected_interface_id BIGINT) '
        || 'RETURNS TABLE ('
        || 'output_export_count BIGINT, '
        || 'unresolved_demand_count BIGINT, '
        || 'resolved_demand_count BIGINT, '
        || 'actor_profile_count BIGINT) '
        || 'LANGUAGE plpgsql AS '
        || quote_literal(patched_body);
END;
$migration$;

COMMIT;
