BEGIN;

ALTER TABLE execution.semantic_parser_source
    ADD COLUMN IF NOT EXISTS char_count BIGINT NOT NULL DEFAULT 0
        CHECK (char_count >= 0);

ALTER TABLE execution.semantic_parser_partition
    ADD COLUMN IF NOT EXISTS owner_start_byte BIGINT NOT NULL DEFAULT 0
        CHECK (owner_start_byte >= 0),
    ADD COLUMN IF NOT EXISTS owner_end_byte BIGINT NOT NULL DEFAULT 0
        CHECK (owner_end_byte >= owner_start_byte),
    ADD COLUMN IF NOT EXISTS context_start_byte BIGINT NOT NULL DEFAULT 0
        CHECK (context_start_byte >= 0),
    ADD COLUMN IF NOT EXISTS context_end_byte BIGINT NOT NULL DEFAULT 0
        CHECK (context_end_byte >= context_start_byte);

ALTER TABLE execution.semantic_parser_partition
    DROP CONSTRAINT IF EXISTS semantic_parser_partition_byte_ownership_check;
ALTER TABLE execution.semantic_parser_partition
    ADD CONSTRAINT semantic_parser_partition_byte_ownership_check CHECK (
        context_start_byte <= owner_start_byte
        AND context_end_byte >= owner_end_byte
    );

COMMIT;
