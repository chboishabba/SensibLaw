BEGIN;

ALTER TABLE execution.semantic_parser_token
    ADD COLUMN IF NOT EXISTS sentence_id BIGINT;

ALTER TABLE execution.semantic_parser_token
    DROP CONSTRAINT IF EXISTS semantic_parser_token_sentence_id_fkey;
ALTER TABLE execution.semantic_parser_token
    ADD CONSTRAINT semantic_parser_token_sentence_id_fkey
    FOREIGN KEY (sentence_id)
    REFERENCES execution.semantic_parser_sentence(sentence_id)
    ON DELETE CASCADE
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE execution.semantic_parser_token
    DROP CONSTRAINT IF EXISTS semantic_parser_token_numeric_representation_ck;
ALTER TABLE execution.semantic_parser_token
    ADD CONSTRAINT semantic_parser_token_numeric_representation_ck CHECK (
        (representation_version = 1 AND orth_ref IS NOT NULL)
        OR
        (
            representation_version = 2
            AND sentence_id IS NOT NULL
            AND orth_symbol_id IS NOT NULL
            AND lemma_symbol_id IS NOT NULL
            AND pos_symbol_id IS NOT NULL
            AND tag_symbol_id IS NOT NULL
            AND dependency_symbol_id IS NOT NULL
            AND orth_ref IS NULL
            AND lemma_ref IS NULL
            AND pos_ref IS NULL
            AND tag_ref IS NULL
            AND dependency_ref IS NULL
        )
    );

CREATE INDEX IF NOT EXISTS semantic_parser_token_sentence_id_idx
    ON execution.semantic_parser_token
       (sentence_id, local_token_ordinal, token_id);
CREATE INDEX IF NOT EXISTS semantic_parser_token_numeric_dependency_id_idx
    ON execution.semantic_parser_token
       (sentence_id, head_token_id, dependency_symbol_id, token_id);

COMMIT;
