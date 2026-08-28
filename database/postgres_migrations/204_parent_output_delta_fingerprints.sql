BEGIN;

-- The Agda hierarchy receipt counts emitted semantic deltas, not dirty input
-- keys and not physical DELETE/INSERT churn.  Persist one fingerprint per
-- parent-output key fibre so propagation stops when local reduction reaches the
-- same parent boundary value.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_parent_output_fingerprint (
    interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    key_family SMALLINT NOT NULL CHECK (key_family BETWEEN 1 AND 5),
    key_a BIGINT NOT NULL,
    key_b BIGINT NOT NULL DEFAULT 0,
    key_c BIGINT NOT NULL DEFAULT 0,
    fibre_digest BYTEA NOT NULL CHECK (octet_length(fibre_digest) = 32),
    PRIMARY KEY (interface_id, key_family, key_a, key_b, key_c)
);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_parent_output_fingerprints(
    selected_interface_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    changed_count BIGINT := 0;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS pg_temp.numeric_pnf_current_output_fingerprint (
        interface_id BIGINT NOT NULL,
        key_family SMALLINT NOT NULL,
        key_a BIGINT NOT NULL,
        key_b BIGINT NOT NULL,
        key_c BIGINT NOT NULL,
        fibre_digest BYTEA NOT NULL,
        PRIMARY KEY (interface_id, key_family, key_a, key_b, key_c)
    ) ON COMMIT DROP;
    TRUNCATE pg_temp.numeric_pnf_current_output_fingerprint;

    INSERT INTO pg_temp.numeric_pnf_current_output_fingerprint
        (interface_id, key_family, key_a, key_b, key_c, fibre_digest)
    SELECT export.interface_id,
           CASE export.target_kind
               WHEN 1 THEN 1
               WHEN 2 THEN 2
               WHEN 3 THEN 3
               ELSE 5
           END::SMALLINT,
           CASE WHEN export.target_kind IN (1, 2, 3)
                THEN export.target_id ELSE export.export_kind END,
           CASE WHEN export.target_kind IN (1, 2, 3)
                THEN 0 ELSE export.target_kind END,
           CASE WHEN export.target_kind IN (1, 2, 3)
                THEN 0 ELSE export.target_id END,
           digest(
               convert_to(
                   concat_ws(
                       '|',
                       export.export_kind::TEXT,
                       export.target_kind::TEXT,
                       export.target_id::TEXT,
                       COALESCE(export.key_symbol_id, 0)::TEXT,
                       COALESCE(export.role_symbol_id, 0)::TEXT,
                       COALESCE(export.residual_type_symbol_id, 0)::TEXT,
                       export.rank::TEXT,
                       export.promotion_score::TEXT,
                       export.scope_class::TEXT,
                       COALESCE(export.origin_interface_id, 0)::TEXT,
                       export.outward_required::TEXT
                   ),
                   'UTF8'
               ),
               'sha256'
           )
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id = selected_interface_id;

    INSERT INTO pg_temp.numeric_pnf_current_output_fingerprint
        (interface_id, key_family, key_a, key_b, key_c, fibre_digest)
    SELECT profile.interface_id,
           4,
           profile.object_id,
           COALESCE(profile.role_symbol_id, 0),
           COALESCE(profile.factor_type_symbol_id, 0),
           digest(
               convert_to(
                   concat_ws(
                       '|',
                       profile.object_id::TEXT,
                       COALESCE(profile.object_kind_symbol_id, 0)::TEXT,
                       COALESCE(profile.role_symbol_id, 0)::TEXT,
                       COALESCE(profile.factor_type_symbol_id, 0)::TEXT,
                       COALESCE(profile.predicate_symbol_id, 0)::TEXT,
                       profile.occurrence_count::TEXT,
                       profile.first_start_char::TEXT,
                       profile.last_end_char::TEXT,
                       profile.promotion_score::TEXT
                   ),
                   'UTF8'
               ),
               'sha256'
           )
      FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
    ON CONFLICT (interface_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET fibre_digest = digest(
        convert_to(
            encode(
                pg_temp.numeric_pnf_current_output_fingerprint.fibre_digest,
                'hex'
            ) || encode(EXCLUDED.fibre_digest, 'hex'),
            'UTF8'
        ),
        'sha256'
    );

    SELECT count(*)
      INTO changed_count
      FROM (
          SELECT COALESCE(current.key_family, prior.key_family) AS key_family,
                 COALESCE(current.key_a, prior.key_a) AS key_a,
                 COALESCE(current.key_b, prior.key_b) AS key_b,
                 COALESCE(current.key_c, prior.key_c) AS key_c,
                 current.fibre_digest AS current_digest,
                 prior.fibre_digest AS prior_digest
            FROM pg_temp.numeric_pnf_current_output_fingerprint AS current
            FULL OUTER JOIN execution.semantic_pnf_parent_output_fingerprint AS prior
              ON prior.interface_id = selected_interface_id
             AND prior.key_family = current.key_family
             AND prior.key_a = current.key_a
             AND prior.key_b = current.key_b
             AND prior.key_c = current.key_c
           WHERE current.interface_id = selected_interface_id
              OR prior.interface_id = selected_interface_id
      ) AS compared
     WHERE compared.current_digest IS DISTINCT FROM compared.prior_digest;

    DELETE FROM execution.semantic_pnf_parent_output_fingerprint
     WHERE interface_id = selected_interface_id;
    INSERT INTO execution.semantic_pnf_parent_output_fingerprint
        (interface_id, key_family, key_a, key_b, key_c, fibre_digest)
    SELECT interface_id, key_family, key_a, key_b, key_c, fibre_digest
      FROM pg_temp.numeric_pnf_current_output_fingerprint
     WHERE interface_id = selected_interface_id;

    RETURN changed_count;
END;
$$;

-- Tighten the structural bridge: enforce the explicit C bound on accumulated
-- exact object/factor/demand families as well as on touched work, and derive D
-- from changed reduced-output fibres rather than from touched input keys.
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

    SELECT
        (SELECT count(*)
           FROM execution.semantic_pnf_parent_delta_projection
          WHERE parent_region_id = selected_region_id)
        +
        (SELECT count(*)
           FROM execution.semantic_pnf_parent_actor_delta_projection
          WHERE parent_region_id = selected_region_id)
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
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id AND target_kind = 1
          UNION
          SELECT 2, target_id, 0, 0
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id AND target_kind = 2
          UNION
          SELECT 3, target_id, 0, 0
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id AND target_kind = 3
          UNION
          SELECT 4, object_id, COALESCE(role_symbol_id, 0),
                 COALESCE(factor_type_symbol_id, 0)
            FROM execution.semantic_pnf_parent_actor_delta_projection
           WHERE parent_region_id = selected_region_id
          UNION
          SELECT 5, export_kind, target_kind, target_id
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id
             AND target_kind NOT IN (1, 2, 3)
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
      FROM execution.semantic_pnf_parent_affected_key
     WHERE parent_region_id = selected_region_id;

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
        SELECT result.output_export_count,
               result.unresolved_demand_count,
               result.resolved_demand_count,
               result.actor_profile_count
          INTO output_value, unresolved_value, resolved_value, actor_value
          FROM execution.rebuild_numeric_pnf_parent_frontier_delta_input(
              selected_interface_id
          ) AS result;

        emitted_value := execution.refresh_numeric_pnf_parent_output_fingerprints(
            selected_interface_id
        );
        DELETE FROM execution.semantic_pnf_parent_affected_key
         WHERE parent_region_id = selected_region_id;
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

COMMENT ON FUNCTION execution.refresh_numeric_pnf_parent_output_fingerprints(BIGINT) IS
    'Return the exact number of reduced parent boundary key fibres whose value changed since the prior reduction, including removed fibres.';

COMMIT;
