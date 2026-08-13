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

-- Zero is execution-level absence.  Generated NULLIF projections retain
-- referential integrity for every concrete nonzero symbol without making the
-- hot insertion trigger perform catalog lookups per actor summary.
ALTER TABLE execution.semantic_pnf_actor_profile
    ADD COLUMN IF NOT EXISTS object_kind_symbol_fk BIGINT
        GENERATED ALWAYS AS (
            NULLIF(object_kind_symbol_id, 0)
        ) STORED
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS role_symbol_fk BIGINT
        GENERATED ALWAYS AS (
            NULLIF(role_symbol_id, 0)
        ) STORED
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS factor_type_symbol_fk BIGINT
        GENERATED ALWAYS AS (
            NULLIF(factor_type_symbol_id, 0)
        ) STORED
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS predicate_symbol_fk BIGINT
        GENERATED ALWAYS AS (
            NULLIF(predicate_symbol_id, 0)
        ) STORED
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT;

COMMIT;
