BEGIN;

ALTER TABLE execution.semantic_parser_token
    DROP CONSTRAINT IF EXISTS semantic_parser_token_head_token_ref_fkey;
ALTER TABLE execution.semantic_parser_token
    ADD CONSTRAINT semantic_parser_token_head_token_ref_fkey
    FOREIGN KEY (head_token_ref)
    REFERENCES execution.semantic_parser_token(token_ref)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

COMMIT;
