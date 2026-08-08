BEGIN;

ALTER TABLE execution.semantic_typed_value_root
    DROP CONSTRAINT IF EXISTS semantic_typed_value_root_root_kind_check;

ALTER TABLE execution.semantic_typed_value_root
    ADD CONSTRAINT semantic_typed_value_root_root_kind_check
    CHECK (
        root_kind IN (
            'mapping', 'sequence', 'text', 'integer',
            'float', 'boolean', 'bytes', 'null'
        )
    );

COMMIT;
