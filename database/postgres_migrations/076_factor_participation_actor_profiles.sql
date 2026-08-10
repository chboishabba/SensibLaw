BEGIN;

-- Standalone object exports establish identity/kind summaries.  Every explicit
-- factor participation must additionally establish the relational profile that
-- typed demands consume: role, factor type and predicate.  Keep this statement
-- level so bulk hyperedge writes remain set based.
CREATE OR REPLACE FUNCTION execution.capture_numeric_pnf_factor_actor_profiles()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_actor_profile
        (interface_id, object_id, object_kind_symbol_id,
         role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
         occurrence_count, first_start_char, last_end_char,
         promotion_score)
    SELECT interface.interface_id,
           object.object_id,
           object.object_kind_symbol_id,
           edge.role_symbol_id,
           factor.factor_type_symbol_id,
           factor.predicate_symbol_id,
           count(*)::BIGINT,
           min(region.start_char),
           max(region.end_char),
           max(object.promotion_score)
      FROM inserted_edge AS edge
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = edge.factor_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = edge.object_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = object.region_id
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = object.region_id
     GROUP BY interface.interface_id,
              object.object_id,
              object.object_kind_symbol_id,
              edge.role_symbol_id,
              factor.factor_type_symbol_id,
              factor.predicate_symbol_id
    ON CONFLICT (
        interface_id, object_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id
    ) DO UPDATE SET
        object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
        occurrence_count = GREATEST(
            execution.semantic_pnf_actor_profile.occurrence_count,
            EXCLUDED.occurrence_count
        ),
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

DROP TRIGGER IF EXISTS semantic_pnf_factor_actor_profile
    ON execution.semantic_pnf_hyperedge;
CREATE TRIGGER semantic_pnf_factor_actor_profile
AFTER INSERT ON execution.semantic_pnf_hyperedge
REFERENCING NEW TABLE AS inserted_edge
FOR EACH STATEMENT
EXECUTE FUNCTION execution.capture_numeric_pnf_factor_actor_profiles();

-- Backfill upgraded databases set-wise.  One profile represents one local
-- object participating under a particular role/factor/predicate signature.
INSERT INTO execution.semantic_pnf_actor_profile
    (interface_id, object_id, object_kind_symbol_id,
     role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
     occurrence_count, first_start_char, last_end_char,
     promotion_score)
SELECT interface.interface_id,
       object.object_id,
       object.object_kind_symbol_id,
       edge.role_symbol_id,
       factor.factor_type_symbol_id,
       factor.predicate_symbol_id,
       count(*)::BIGINT,
       min(region.start_char),
       max(region.end_char),
       max(object.promotion_score)
  FROM execution.semantic_pnf_hyperedge AS edge
  JOIN execution.semantic_pnf_factor AS factor
    ON factor.factor_id = edge.factor_id
  JOIN execution.semantic_pnf_object AS object
    ON object.object_id = edge.object_id
  JOIN execution.semantic_pnf_region AS region
    ON region.region_id = object.region_id
  JOIN execution.semantic_pnf_interface AS interface
    ON interface.region_id = object.region_id
 GROUP BY interface.interface_id,
          object.object_id,
          object.object_kind_symbol_id,
          edge.role_symbol_id,
          factor.factor_type_symbol_id,
          factor.predicate_symbol_id
ON CONFLICT (
    interface_id, object_id, role_symbol_id,
    factor_type_symbol_id, predicate_symbol_id
) DO UPDATE SET
    object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
    occurrence_count = GREATEST(
        execution.semantic_pnf_actor_profile.occurrence_count,
        EXCLUDED.occurrence_count
    ),
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
