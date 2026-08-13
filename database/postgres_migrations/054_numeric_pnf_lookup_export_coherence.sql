BEGIN;

-- An interface lookup is a searchable projection of an admitted interface
-- export.  It must never re-introduce a child object, factor, or demand that the
-- parent promotion/reconciliation policy rejected.
CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_interface_lookup()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_interface_export AS export
         WHERE export.interface_id = NEW.interface_id
           AND export.target_kind = NEW.target_kind
           AND export.target_id = NEW.target_id
    ) THEN
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_lookup_promotion
    ON execution.semantic_pnf_interface_lookup;
CREATE TRIGGER semantic_pnf_parent_lookup_promotion
BEFORE INSERT ON execution.semantic_pnf_interface_lookup
FOR EACH ROW
EXECUTE FUNCTION execution.admit_numeric_pnf_interface_lookup();

-- Remove any historical lookup rows whose corresponding export was not
-- admitted.  This is idempotent and preserves all lower-level evidence in the
-- child interfaces and provenance tables.
DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
 WHERE NOT EXISTS (
     SELECT 1
       FROM execution.semantic_pnf_interface_export AS export
      WHERE export.interface_id = lookup.interface_id
        AND export.target_kind = lookup.target_kind
        AND export.target_id = lookup.target_id
 );

COMMIT;
