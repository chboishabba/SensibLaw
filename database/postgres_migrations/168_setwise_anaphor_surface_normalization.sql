BEGIN;

-- 168: anaphor spelling is surface evidence, not an identity key. Migration 064
-- enforced that boundary with a BEFORE-row normalizer. A later setwise rewrite
-- tried to perform the normalization from AFTER statement triggers by UPDATEing
-- execution.semantic_pnf_demand itself so the other UPDATE projections would
-- run again. That creates a recursive trigger dependency on the same authority
-- table and makes clean migration replay depend on accidental convergence of
-- the whole UPDATE-trigger stack.
--
-- Restore the acyclic form instead: canonicalize NEW before the row is written.
-- All downstream INSERT/UPDATE projections then observe the final demand row
-- exactly once. Surface spelling is preserved in surface_lexical_symbol_id,
-- while lexical_symbol_id is absent as an identity constraint.

DROP TRIGGER IF EXISTS semantic_pnf_anaphor_surface_normalisation
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS zzz_semantic_pnf_anaphor_surface_insert_batch
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS zzz_semantic_pnf_anaphor_surface_update_batch
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_anaphor_surface_insert_before
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_anaphor_surface_update_before
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_surface()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    constant_row execution.semantic_pnf_anaphor_projection_constant%ROWTYPE;
BEGIN
    IF NEW.lexical_symbol_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT constant.*
      INTO constant_row
      FROM execution.semantic_pnf_anaphor_projection_constant AS constant
     WHERE constant.singleton;

    IF NEW.residual_type_symbol_id=constant_row.anaphor_residual_type_symbol_id THEN
        NEW.surface_lexical_symbol_id := COALESCE(
            NEW.surface_lexical_symbol_id,
            NEW.lexical_symbol_id
        );
        NEW.lexical_symbol_id := NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER semantic_pnf_anaphor_surface_insert_before
BEFORE INSERT ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (NEW.lexical_symbol_id IS NOT NULL)
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_surface();

CREATE TRIGGER semantic_pnf_anaphor_surface_update_before
BEFORE UPDATE OF residual_type_symbol_id, lexical_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (
    NEW.lexical_symbol_id IS NOT NULL
    AND (
        NEW.residual_type_symbol_id IS DISTINCT FROM OLD.residual_type_symbol_id
        OR NEW.lexical_symbol_id IS DISTINCT FROM OLD.lexical_symbol_id
    )
)
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_surface();

-- Repair upgraded databases. This ordinary migration UPDATE is not a trigger
-- callback: the BEFORE normalizer performs no table write, so the downstream
-- UPDATE projections see the repaired row once rather than through recursion.
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

-- Historical interface rows may predate the canonical BEFORE-row rule. Repair
-- those derived surfaces once during migration. New writes need no corrective
-- second pass because their demand row is normalized before projection.
UPDATE execution.semantic_pnf_interface_export AS export
   SET key_symbol_id=NULL
  FROM execution.semantic_pnf_demand AS demand,
       execution.semantic_pnf_anaphor_projection_constant AS constant
 WHERE constant.singleton
   AND export.target_kind=3
   AND export.target_id=demand.demand_id
   AND demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
   AND demand.lexical_symbol_id IS NULL
   AND demand.surface_lexical_symbol_id IS NOT NULL
   AND export.key_symbol_id IS NOT NULL;

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
