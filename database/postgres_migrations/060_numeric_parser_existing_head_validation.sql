BEGIN;

-- Migration 052 protects new writes with a deferred semantic constraint.  This
-- migration closes the upgrade gap by validating every pre-existing v2 token
-- before adding a version-gated non-null check.
DO $$
DECLARE
    invalid_token_id BIGINT;
BEGIN
    SELECT token.token_id
      INTO invalid_token_id
      FROM execution.semantic_parser_token AS token
      LEFT JOIN execution.semantic_parser_token AS head
        ON head.token_id = token.head_token_id
     WHERE token.representation_version = 2
       AND (
           token.head_token_id IS NULL
           OR head.token_id IS NULL
           OR head.representation_version <> 2
           OR head.sentence_id IS DISTINCT FROM token.sentence_id
           OR (
               token.head_token_id = token.token_id
               AND (
                   token.head_start_char IS DISTINCT FROM token.start_char
                   OR token.head_end_char IS DISTINCT FROM token.end_char
               )
           )
           OR (
               token.head_token_id <> token.token_id
               AND (
                   token.head_start_char IS DISTINCT FROM head.start_char
                   OR token.head_end_char IS DISTINCT FROM head.end_char
               )
           )
       )
     ORDER BY token.token_id
     LIMIT 1;

    IF invalid_token_id IS NOT NULL THEN
        RAISE EXCEPTION
            'existing numeric parser token % violates dependency-head authority',
            invalid_token_id;
    END IF;
END;
$$;

-- New writes keep the deferred head-integrity constraint trigger from 052:
-- a v2 token is inserted before its head token id is known and resolved by a
-- later UPDATE in the same fenced transaction, so a non-deferrable CHECK here
-- would reject the legitimate insert path.  The constraint trigger validates
-- head presence and coordinates for every committed v2 row instead.

COMMIT;
