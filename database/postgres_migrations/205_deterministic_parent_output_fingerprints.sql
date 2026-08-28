BEGIN;

-- Actor fibres may contain several predicate rows for the same
-- (object, role, factor-type) affected key.  Hash their sorted canonical row
-- encoding as one fibre rather than depending on INSERT/ON-CONFLICT row order.
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
                   string_agg(
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
                       ',' ORDER BY
                           COALESCE(profile.predicate_symbol_id, 0),
                           profile.object_id,
                           profile.first_start_char,
                           profile.last_end_char
                   ),
                   'UTF8'
               ),
               'sha256'
           )
      FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
     GROUP BY profile.interface_id,
              profile.object_id,
              profile.role_symbol_id,
              profile.factor_type_symbol_id;

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

COMMIT;
