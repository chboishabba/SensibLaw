BEGIN;

-- 179: migration 062 has a second demand × actor-profile exposure before
-- candidate generation. Low-salience actor pruning asks, for every parent
-- profile, whether any unresolved child object demand could request it. The
-- historical correlated NOT EXISTS can therefore repeatedly scan the same child
-- demand fibre once per profile.
--
-- Preserve that retention predicate exactly, including its deliberate omission
-- of lexical matching: a low-salience actor survives when any unresolved child
-- object demand matches the profile's optional object-kind, role and factor-type
-- constraints. Build that relation once by indexed key intersection instead.

CREATE OR REPLACE FUNCTION execution.indexed_numeric_pnf_demanded_actor_profiles(
    selected_region_id BIGINT,
    selected_interface_id BIGINT
)
RETURNS TABLE (
    object_id BIGINT,
    role_symbol_id BIGINT,
    factor_type_symbol_id BIGINT,
    predicate_symbol_id BIGINT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    -- The actor-retention predicate intentionally ignores lexical identity. It
    -- may use the persisted constraint fibre only when key kinds 1/2/4 exactly
    -- represent the canonical factor/object/role columns of the child demands.
    IF EXISTS (
        WITH child_demand AS MATERIALIZED (
            SELECT DISTINCT demand.demand_id,
                   demand.expected_object_kind_symbol_id,
                   demand.role_symbol_id,
                   demand.expected_factor_type_symbol_id
              FROM execution.semantic_pnf_region AS child_region
              JOIN execution.semantic_pnf_interface AS child_interface
                ON child_interface.region_id = child_region.region_id
              JOIN execution.semantic_pnf_interface_export AS demand_export
                ON demand_export.interface_id = child_interface.interface_id
               AND demand_export.target_kind = 3
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = demand_export.target_id
             WHERE child_region.parent_region_id = selected_region_id
               AND demand.state IN (1, 3)
               AND demand.expected_target_kind = 1
        ),
        expected_key AS (
            SELECT child_demand.demand_id,
                   1::SMALLINT AS key_kind,
                   child_demand.expected_factor_type_symbol_id AS key_a,
                   0::BIGINT AS key_b
              FROM child_demand
             WHERE child_demand.expected_factor_type_symbol_id IS NOT NULL
            UNION ALL
            SELECT child_demand.demand_id,
                   2::SMALLINT,
                   child_demand.expected_object_kind_symbol_id,
                   0::BIGINT
              FROM child_demand
             WHERE child_demand.expected_object_kind_symbol_id IS NOT NULL
            UNION ALL
            SELECT child_demand.demand_id,
                   4::SMALLINT,
                   child_demand.role_symbol_id,
                   0::BIGINT
              FROM child_demand
             WHERE child_demand.role_symbol_id IS NOT NULL
        ),
        actual_key AS (
            SELECT constraint_row.demand_id,
                   constraint_row.key_kind,
                   constraint_row.key_a,
                   constraint_row.key_b
              FROM child_demand AS demand
              JOIN execution.semantic_pnf_demand_constraint AS constraint_row
                ON constraint_row.demand_id = demand.demand_id
             WHERE constraint_row.required
               AND constraint_row.polarity = 1
               AND constraint_row.key_kind IN (1, 2, 4)
        ),
        difference AS (
            (SELECT * FROM expected_key EXCEPT SELECT * FROM actual_key)
            UNION ALL
            (SELECT * FROM actual_key EXCEPT SELECT * FROM expected_key)
        )
        SELECT 1 FROM difference LIMIT 1
    ) THEN
        RAISE EXCEPTION
            'numeric PNF actor-retention constraint fibre disagrees with canonical child demands for region %',
            selected_region_id;
    END IF;

    RETURN QUERY
    WITH child_demand AS MATERIALIZED (
        SELECT DISTINCT demand.demand_id,
               demand.expected_object_kind_symbol_id,
               demand.role_symbol_id,
               demand.expected_factor_type_symbol_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
          JOIN execution.semantic_pnf_interface_export AS demand_export
            ON demand_export.interface_id = child_interface.interface_id
           AND demand_export.target_kind = 3
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
         WHERE child_region.parent_region_id = selected_region_id
           AND demand.state IN (1, 3)
           AND demand.expected_target_kind = 1
    ),
    required_key AS MATERIALIZED (
        SELECT constraint_row.demand_id,
               constraint_row.key_kind,
               constraint_row.key_a,
               constraint_row.key_b
          FROM child_demand AS demand
          JOIN execution.semantic_pnf_demand_constraint AS constraint_row
            ON constraint_row.demand_id = demand.demand_id
         WHERE constraint_row.required
           AND constraint_row.polarity = 1
           AND constraint_row.key_kind IN (1, 2, 4)
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
               profile.predicate_symbol_id
          FROM execution.semantic_pnf_actor_profile AS profile
         WHERE profile.interface_id = selected_interface_id
    ),
    profile_key AS MATERIALIZED (
        SELECT profile.object_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               key.key_kind,
               key.key_a,
               0::BIGINT AS key_b
          FROM profile_base AS profile
          CROSS JOIN LATERAL (
              VALUES
                  (1::SMALLINT, profile.factor_type_symbol_id),
                  (2::SMALLINT, profile.object_kind_symbol_id),
                  (4::SMALLINT, profile.role_symbol_id)
          ) AS key(key_kind, key_a)
         WHERE key.key_a IS NOT NULL
    ),
    matched_profile AS MATERIALIZED (
        SELECT required_key.demand_id,
               profile.object_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               count(*)::BIGINT AS matched_count
          FROM required_key
          JOIN profile_key AS profile
            ON profile.key_kind = required_key.key_kind
           AND profile.key_a = required_key.key_a
           AND profile.key_b = required_key.key_b
         GROUP BY required_key.demand_id,
                  profile.object_id,
                  profile.role_symbol_id,
                  profile.factor_type_symbol_id,
                  profile.predicate_symbol_id
    ),
    indexed_profile AS (
        SELECT matched.object_id,
               matched.role_symbol_id,
               matched.factor_type_symbol_id,
               matched.predicate_symbol_id
          FROM matched_profile AS matched
          JOIN required_count AS required
            ON required.demand_id = matched.demand_id
           AND required.required_count = matched.matched_count
    ),
    broad_profile AS (
        -- No kind/role/factor constraint means every profile is requestable.
        -- This is migration 062's wildcard semantics, not absence evidence.
        SELECT profile.object_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id
          FROM child_demand AS demand
          LEFT JOIN required_count AS required
            ON required.demand_id = demand.demand_id
          CROSS JOIN profile_base AS profile
         WHERE required.demand_id IS NULL
    )
    SELECT DISTINCT
           retained.object_id,
           retained.role_symbol_id,
           retained.factor_type_symbol_id,
           retained.predicate_symbol_id
      FROM (
          SELECT * FROM indexed_profile
          UNION ALL
          SELECT * FROM broad_profile
      ) AS retained;
END;
$$;

DO $migration$
DECLARE
    source_body TEXT;
    patched_body TEXT;
    delete_start INTEGER;
    next_stage_start INTEGER;
    old_delete_block TEXT;
    historical_boundary BOOLEAN := FALSE;
    delta_boundary BOOLEAN := FALSE;
    replacement TEXT := E'    DELETE FROM execution.semantic_pnf_actor_profile AS profile\n'
        || E'     WHERE profile.interface_id = selected_interface_id\n'
        || E'       AND profile.promotion_score < COALESCE(threshold_value, 0)\n'
        || E'       AND profile.occurrence_count < 2\n'
        || E'       AND NOT EXISTS (\n'
        || E'           SELECT 1\n'
        || E'             FROM execution.indexed_numeric_pnf_demanded_actor_profiles(\n'
        || E'                 selected_region_id, selected_interface_id\n'
        || E'             ) AS demanded\n'
        || E'            WHERE demanded.object_id = profile.object_id\n'
        || E'              AND demanded.role_symbol_id = profile.role_symbol_id\n'
        || E'              AND demanded.factor_type_symbol_id = profile.factor_type_symbol_id\n'
        || E'              AND demanded.predicate_symbol_id = profile.predicate_symbol_id\n'
        || E'       );\n\n';
BEGIN
    SELECT procedure.prosrc
      INTO source_body
      FROM pg_proc AS procedure
      JOIN pg_namespace AS namespace
        ON namespace.oid = procedure.pronamespace
     WHERE namespace.nspname = 'execution'
       AND procedure.proname = 'rebuild_numeric_pnf_parent_frontier_canonical'
       AND procedure.pronargs = 1
       AND procedure.proargtypes[0] = 'int8'::regtype::oid;

    IF source_body IS NULL THEN
        RAISE EXCEPTION
            'migration 179 cannot find execution.rebuild_numeric_pnf_parent_frontier_canonical(bigint)';
    END IF;

    IF strpos(
        source_body,
        'execution.indexed_numeric_pnf_demanded_actor_profiles('
    ) > 0 THEN
        RETURN;
    END IF;

    delete_start := strpos(
        source_body,
        E'    DELETE FROM execution.semantic_pnf_actor_profile AS profile\n'
        || E'     WHERE profile.interface_id = selected_interface_id\n'
        || E'       AND profile.promotion_score < COALESCE(threshold_value, 0)\n'
    );

    -- Migration 062 and the C3 delta-fed reducer use the same semantic stage
    -- boundary but different source-carrier prose. Recognize both exact owners;
    -- do not weaken this to an arbitrary later comment or substring.
    next_stage_start := strpos(
        source_body,
        E'    -- Unresolved holes always cross the boundary.  Resolved demands disappear.\n'
    );
    IF next_stage_start = 0 THEN
        next_stage_start := strpos(
            source_body,
            E'    -- Unresolved holes cross the boundary from the transported delta carrier.\n'
        );
    END IF;

    IF delete_start = 0
       OR next_stage_start = 0
       OR next_stage_start <= delete_start THEN
        RAISE EXCEPTION
            'migration 179 cannot locate canonical actor-retention block';
    END IF;

    old_delete_block := substr(
        source_body,
        delete_start,
        next_stage_start - delete_start
    );

    historical_boundary :=
        strpos(
            old_delete_block,
            'JOIN execution.semantic_pnf_interface_export AS demand_export'
        ) > 0;
    delta_boundary :=
        strpos(
            old_delete_block,
            'FROM execution.semantic_pnf_parent_delta_projection AS demand_export'
        ) > 0
        AND strpos(
            old_delete_block,
            'demand_export.parent_region_id = selected_region_id'
        ) > 0
        AND strpos(old_delete_block, 'demand_export.target_kind = 3') > 0;

    IF NOT (historical_boundary OR delta_boundary)
       OR strpos(old_delete_block, 'demand.expected_target_kind = 1') = 0
       OR strpos(
           old_delete_block,
           'demand.expected_object_kind_symbol_id IS NULL'
       ) = 0
       OR strpos(old_delete_block, 'demand.role_symbol_id IS NULL') = 0
       OR strpos(
           old_delete_block,
           'demand.expected_factor_type_symbol_id IS NULL'
       ) = 0 THEN
        RAISE EXCEPTION
            'migration 179 refuses to replace an unrecognised actor-retention implementation';
    END IF;

    patched_body := substr(source_body, 1, delete_start - 1)
        || replacement
        || substr(source_body, next_stage_start);

    EXECUTE
        'CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier_canonical('
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
