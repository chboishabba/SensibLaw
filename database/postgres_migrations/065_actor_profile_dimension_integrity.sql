BEGIN;

UPDATE execution.semantic_pnf_actor_profile
   SET object_kind_symbol_id = COALESCE(object_kind_symbol_id, 0),
       role_symbol_id = COALESCE(role_symbol_id, 0),
       factor_type_symbol_id = COALESCE(factor_type_symbol_id, 0),
       predicate_symbol_id = COALESCE(predicate_symbol_id, 0);

ALTER TABLE execution.semantic_pnf_actor_profile
    ALTER COLUMN object_kind_symbol_id SET NOT NULL,
    ALTER COLUMN role_symbol_id SET NOT NULL,
    ALTER COLUMN factor_type_symbol_id SET NOT NULL,
    ALTER COLUMN predicate_symbol_id SET NOT NULL;

ALTER TABLE execution.semantic_pnf_actor_profile
    DROP CONSTRAINT IF EXISTS semantic_pnf_actor_profile_dimension_ck;
ALTER TABLE execution.semantic_pnf_actor_profile
    ADD CONSTRAINT semantic_pnf_actor_profile_dimension_ck CHECK (
        object_kind_symbol_id >= 0
        AND role_symbol_id >= 0
        AND factor_type_symbol_id >= 0
        AND predicate_symbol_id >= 0
    );

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

    IF NEW.object_kind_symbol_id <> 0
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_symbol
            WHERE symbol_id = NEW.object_kind_symbol_id
              AND kind_id = 14
       ) THEN
        RAISE EXCEPTION
            'actor profile object-kind symbol % is not kind 14',
            NEW.object_kind_symbol_id;
    END IF;
    IF NEW.role_symbol_id <> 0
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_symbol
            WHERE symbol_id = NEW.role_symbol_id
              AND kind_id = 12
       ) THEN
        RAISE EXCEPTION
            'actor profile role symbol % is not kind 12',
            NEW.role_symbol_id;
    END IF;
    IF NEW.factor_type_symbol_id <> 0
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_symbol
            WHERE symbol_id = NEW.factor_type_symbol_id
              AND kind_id = 10
       ) THEN
        RAISE EXCEPTION
            'actor profile factor-type symbol % is not kind 10',
            NEW.factor_type_symbol_id;
    END IF;
    IF NEW.predicate_symbol_id <> 0
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_symbol
            WHERE symbol_id = NEW.predicate_symbol_id
              AND kind_id = 11
       ) THEN
        RAISE EXCEPTION
            'actor profile predicate symbol % is not kind 11',
            NEW.predicate_symbol_id;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
