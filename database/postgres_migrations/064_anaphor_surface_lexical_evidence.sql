BEGIN;

-- Pronoun/anaphor spelling is surface evidence for the typed hole, not an
-- identity key that the eventual actor witness must share.  Preserve it
-- separately and remove it from exact lexical candidate constraints.
ALTER TABLE execution.semantic_pnf_demand
    ADD COLUMN IF NOT EXISTS surface_lexical_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_surface()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    anaphor_residual_id BIGINT;
BEGIN
    SELECT symbol_id
      INTO anaphor_residual_id
      FROM execution.semantic_symbol
     WHERE kind_id = 13
       AND symbol_text = 'anaphor_unresolved';

    IF anaphor_residual_id IS NOT NULL
       AND NEW.residual_type_symbol_id = anaphor_residual_id
       AND NEW.lexical_symbol_id IS NOT NULL THEN
        NEW.surface_lexical_symbol_id := COALESCE(
            NEW.surface_lexical_symbol_id,
            NEW.lexical_symbol_id
        );
        NEW.lexical_symbol_id := NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_anaphor_surface_normalisation
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_anaphor_surface_normalisation
BEFORE INSERT OR UPDATE OF lexical_symbol_id, residual_type_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_surface();

WITH anaphor AS (
    SELECT symbol_id
      FROM execution.semantic_symbol
     WHERE kind_id = 13
       AND symbol_text = 'anaphor_unresolved'
)
UPDATE execution.semantic_pnf_demand AS demand
   SET surface_lexical_symbol_id = COALESCE(
           demand.surface_lexical_symbol_id,
           demand.lexical_symbol_id
       ),
       lexical_symbol_id = NULL
  FROM anaphor
 WHERE demand.residual_type_symbol_id = anaphor.symbol_id
   AND demand.lexical_symbol_id IS NOT NULL;

-- Existing demand exports may still carry the pronoun in key_symbol_id.  The
-- surface remains available on the demand; the searchable boundary must use
-- only true identity keys.
UPDATE execution.semantic_pnf_interface_export AS export
   SET key_symbol_id = NULL
  FROM execution.semantic_pnf_demand AS demand
 WHERE export.target_kind = 3
   AND export.target_id = demand.demand_id
   AND demand.surface_lexical_symbol_id IS NOT NULL
   AND demand.lexical_symbol_id IS NULL;

DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
USING execution.semantic_pnf_demand AS demand
WHERE lookup.target_kind = 3
  AND lookup.target_id = demand.demand_id
  AND lookup.key_kind = 3
  AND demand.surface_lexical_symbol_id IS NOT NULL
  AND demand.lexical_symbol_id IS NULL;

COMMIT;
