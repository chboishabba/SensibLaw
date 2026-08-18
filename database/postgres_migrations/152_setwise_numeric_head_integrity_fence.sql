BEGIN;

-- 152: migration 052's deferred row constraint trigger was the correct generic
-- defence when numeric dependency heads could be filled piecemeal after token
-- insertion. The strict numeric parser path now has a stronger bounded carrier:
-- one COPY statement contains the complete partition token fibre and migration
-- 150 resolves/validates the same-sentence span -> head relation set-wise.
--
-- Do not enqueue two point-query constraint events per token merely to re-read
-- a relation already checked for the complete inserted fibre. Keep the deferred
-- trigger as the fail-closed authority for every writer that does not explicitly
-- hold the set-wise contract. The custom GUC is transaction-local execution
-- state only and is never part of semantic identity.

CREATE OR REPLACE FUNCTION execution.numeric_parser_setwise_head_integrity_ready()
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
SELECT TRUE;
$$;

DROP TRIGGER IF EXISTS semantic_parser_token_head_integrity
    ON execution.semantic_parser_token;
CREATE CONSTRAINT TRIGGER semantic_parser_token_head_integrity
AFTER INSERT OR UPDATE OF
    head_token_id,
    head_start_char,
    head_end_char,
    sentence_id,
    representation_version
ON execution.semantic_parser_token
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
WHEN (
    current_setting(
        'sensiblaw.setwise_numeric_head_integrity',
        TRUE
    ) IS DISTINCT FROM 'on'
)
EXECUTE FUNCTION execution.validate_numeric_parser_head_integrity();

COMMIT;
