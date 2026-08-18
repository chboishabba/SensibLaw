BEGIN;

-- 168: migration 064 normalized anaphor surface spelling with a BEFORE row
-- trigger. The operation is a pure projection of affected demand rows and the
-- numeric anaphor constant installed by 157. Retire the per-demand trigger.
--
-- Because the old trigger ran BEFORE INSERT/UPDATE, later demand-export/index
-- triggers never saw the pronoun spelling as an identity key. The statement
-- projection below therefore repairs those derived rows too, preserving the
-- same final semantic boundary: surface evidence is retained; lexical identity
-- constraint is absent.

DROP TRIGGER IF EXISTS semantic_pnf_anaphor_surface_normalisation
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_surface_inserted_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE execution.semantic_pnf_demand AS demand
       SET surface_lexical_symbol_id=COALESCE(
               demand.surface_lexical_symbol_id,
               inserted.lexical_symbol_id
           ),
           lexical_symbol_id=NULL
      FROM inserted_demand AS inserted
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
     WHERE demand.demand_id=inserted.demand_id
       AND inserted.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
       AND inserted.lexical_symbol_id IS NOT NULL;

    UPDATE execution.semantic_pnf_interface_export AS export
       SET key_symbol_id=NULL
      FROM inserted_demand AS inserted
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
     WHERE export.target_kind=3
       AND export.target_id=inserted.demand_id
       AND inserted.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
       AND inserted.lexical_symbol_id IS NOT NULL
       AND export.key_symbol_id IS NOT NULL;

    DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
    USING inserted_demand AS inserted,
          execution.semantic_pnf_anaphor_projection_constant AS constant
    WHERE constant.singleton
      AND lookup.target_kind=3
      AND lookup.target_id=inserted.demand_id
      AND lookup.key_kind=3
      AND inserted.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
      AND inserted.lexical_symbol_id IS NOT NULL;

    RETURN NULL;
END;
$$;

-- Alphabetical trigger order deliberately places normalization after the other
-- ordinary AFTER INSERT statement projections. The corrective UPDATE is then
-- visible to their UPDATE transition-table paths, so demand constraints/lookup
-- keys converge to the normalized row without row-local work.
DROP TRIGGER IF EXISTS zzz_semantic_pnf_anaphor_surface_insert_batch
    ON execution.semantic_pnf_demand;
CREATE TRIGGER zzz_semantic_pnf_anaphor_surface_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_surface_inserted_batch();

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_surface_updated_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS MATERIALIZED (
        SELECT current.demand_id,
               current.residual_type_symbol_id,
               current.lexical_symbol_id
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.lexical_symbol_id IS NOT NULL
           AND (
               current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
               OR current.residual_type_symbol_id
                    IS DISTINCT FROM prior.residual_type_symbol_id
           )
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET surface_lexical_symbol_id=COALESCE(
               demand.surface_lexical_symbol_id,
               changed.lexical_symbol_id
           ),
           lexical_symbol_id=NULL
      FROM changed
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
     WHERE demand.demand_id=changed.demand_id
       AND changed.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id;

    WITH changed AS MATERIALIZED (
        SELECT current.demand_id,
               current.residual_type_symbol_id,
               current.lexical_symbol_id
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.lexical_symbol_id IS NOT NULL
           AND (
               current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
               OR current.residual_type_symbol_id
                    IS DISTINCT FROM prior.residual_type_symbol_id
           )
    )
    UPDATE execution.semantic_pnf_interface_export AS export
       SET key_symbol_id=NULL
      FROM changed
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
     WHERE export.target_kind=3
       AND export.target_id=changed.demand_id
       AND changed.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
       AND export.key_symbol_id IS NOT NULL;

    WITH changed AS MATERIALIZED (
        SELECT current.demand_id,
               current.residual_type_symbol_id,
               current.lexical_symbol_id
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.lexical_symbol_id IS NOT NULL
           AND (
               current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
               OR current.residual_type_symbol_id
                    IS DISTINCT FROM prior.residual_type_symbol_id
           )
    )
    DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
    USING changed,
          execution.semantic_pnf_anaphor_projection_constant AS constant
    WHERE constant.singleton
      AND lookup.target_kind=3
      AND lookup.target_id=changed.demand_id
      AND lookup.key_kind=3
      AND changed.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS zzz_semantic_pnf_anaphor_surface_update_batch
    ON execution.semantic_pnf_demand;
CREATE TRIGGER zzz_semantic_pnf_anaphor_surface_update_batch
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_surface_updated_batch();

-- Repair upgraded databases using the same final-state rule.
UPDATE execution.semantic_pnf_demand AS demand
   SET surface_lexical_symbol_id=COALESCE(
           demand.surface_lexical_symbol_id,
           demand.lexical_symbol_id
       ),
       lexical_symbol_id=NULL
  FROM execution.semantic_pnf_anaphor_projection_constant AS constant
 WHERE constant.singleton
   AND demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
   AND demand.lexical_symbol_id IS NOT NULL;

UPDATE execution.semantic_pnf_interface_export AS export
   SET key_symbol_id=NULL
  FROM execution.semantic_pnf_demand AS demand,
       execution.semantic_pnf_anaphor_projection_constant AS constant
 WHERE constant.singleton
   AND export.target_kind=3
   AND export.target_id=demand.demand_id
   AND demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
   AND demand.lexical_symbol_id IS NULL
   AND demand.surface_lexical_symbol_id IS NOT NULL;

DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
USING execution.semantic_pnf_demand AS demand,
      execution.semantic_pnf_anaphor_projection_constant AS constant
WHERE constant.singleton
  AND lookup.target_kind=3
  AND lookup.target_id=demand.demand_id
  AND lookup.key_kind=3
  AND demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
  AND demand.lexical_symbol_id IS NULL
  AND demand.surface_lexical_symbol_id IS NOT NULL;

COMMIT;
