BEGIN;

-- Actor-profile dimensions participate in the deterministic primary key.
-- Numeric zero is the canonical absent/unspecified value; semantic symbols
-- begin at one.  This keeps joins compact and makes repeated summaries
-- conflict deterministically instead of fragmenting on SQL NULL semantics.
ALTER TABLE execution.semantic_pnf_actor_profile
    DROP CONSTRAINT IF EXISTS
        semantic_pnf_actor_profile_object_kind_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS
        semantic_pnf_actor_profile_role_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS
        semantic_pnf_actor_profile_factor_type_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS
        semantic_pnf_actor_profile_predicate_symbol_id_fkey;

ALTER TABLE execution.semantic_pnf_actor_profile
    ALTER COLUMN object_kind_symbol_id SET DEFAULT 0,
    ALTER COLUMN role_symbol_id SET DEFAULT 0,
    ALTER COLUMN factor_type_symbol_id SET DEFAULT 0,
    ALTER COLUMN predicate_symbol_id SET DEFAULT 0;

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_actor_profile_key()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.object_kind_symbol_id := COALESCE(NEW.object_kind_symbol_id, 0);
    NEW.role_symbol_id := COALESCE(NEW.role_symbol_id, 0);
    NEW.factor_type_symbol_id := COALESCE(
        NEW.factor_type_symbol_id,
        0
    );
    NEW.predicate_symbol_id := COALESCE(NEW.predicate_symbol_id, 0);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_actor_profile_key_normalisation
    ON execution.semantic_pnf_actor_profile;
CREATE TRIGGER semantic_pnf_actor_profile_key_normalisation
BEFORE INSERT OR UPDATE OF
    object_kind_symbol_id,
    role_symbol_id,
    factor_type_symbol_id,
    predicate_symbol_id
ON execution.semantic_pnf_actor_profile
FOR EACH ROW
EXECUTE FUNCTION execution.normalize_numeric_pnf_actor_profile_key();

COMMIT;
