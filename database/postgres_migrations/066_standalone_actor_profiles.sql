BEGIN;

-- Capture object identities as generic actor summaries in one statement-level
-- operation.  Relational factor participation later enriches the same actor
-- with role/factor/predicate dimensions.  Zero means unspecified, not unknown
-- semantic authority.
CREATE OR REPLACE FUNCTION execution.capture_numeric_pnf_actor_export_profiles()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_actor_profile
        (interface_id, object_id, object_kind_symbol_id,
         role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
         occurrence_count, first_start_char, last_end_char,
         promotion_score)
    SELECT export.interface_id,
           object.object_id,
           object.object_kind_symbol_id,
           0,
           0,
           0,
           1,
           region.start_char,
           region.end_char,
           object.promotion_score
      FROM inserted_export AS export
      JOIN execution.semantic_pnf_object AS object
        ON export.target_kind = 1
       AND object.object_id = export.target_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = object.region_id
    ON CONFLICT (
        interface_id, object_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id
    ) DO UPDATE SET
        object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
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
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_actor_export_profile
    ON execution.semantic_pnf_interface_export;
CREATE TRIGGER semantic_pnf_actor_export_profile
AFTER INSERT ON execution.semantic_pnf_interface_export
REFERENCING NEW TABLE AS inserted_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.capture_numeric_pnf_actor_export_profiles();

-- Backfill current admitted object exports set-wise.  Parent frontier rebuilds
-- remain authoritative and may subsequently prune these generic summaries.
INSERT INTO execution.semantic_pnf_actor_profile
    (interface_id, object_id, object_kind_symbol_id,
     role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
     occurrence_count, first_start_char, last_end_char,
     promotion_score)
SELECT export.interface_id,
       object.object_id,
       object.object_kind_symbol_id,
       0,
       0,
       0,
       1,
       region.start_char,
       region.end_char,
       object.promotion_score
  FROM execution.semantic_pnf_interface_export AS export
  JOIN execution.semantic_pnf_object AS object
    ON export.target_kind = 1
   AND object.object_id = export.target_id
  JOIN execution.semantic_pnf_region AS region
    ON region.region_id = object.region_id
ON CONFLICT (
    interface_id, object_id, role_symbol_id,
    factor_type_symbol_id, predicate_symbol_id
) DO UPDATE SET
    object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
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

COMMIT;
