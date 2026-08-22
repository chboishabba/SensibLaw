BEGIN;

-- 150: one parser partition COPY already contains every numeric token and the
-- declared dependency-head span for that token. Resolve head_token_id for the
-- whole inserted token fibre in one statement-level operation rather than
-- requiring one UPDATE per token after COPY.
--
-- The Python projection still validates parser-specific root semantics and
-- rejects a non-root token whose declared head resolves to itself. This trigger
-- owns only the relational span -> token-id projection and fails closed unless
-- every inserted v2 token has exactly one head token in the same sentence.

CREATE OR REPLACE FUNCTION execution.resolve_numeric_parser_dependency_heads()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM inserted_token AS token
          LEFT JOIN execution.semantic_parser_token AS head
            ON head.sentence_id = token.sentence_id
           AND head.start_char = token.head_start_char
           AND head.end_char = token.head_end_char
           AND head.representation_version = 2
         WHERE token.representation_version = 2
         GROUP BY token.token_id
        HAVING count(head.token_id) <> 1
    ) THEN
        RAISE EXCEPTION
            'numeric parser dependency head is missing or ambiguous in inserted token fibre';
    END IF;

    UPDATE execution.semantic_parser_token AS token
       SET head_token_id = head.token_id
      FROM inserted_token AS inserted
      JOIN execution.semantic_parser_token AS head
        ON head.sentence_id = inserted.sentence_id
       AND head.start_char = inserted.head_start_char
       AND head.end_char = inserted.head_end_char
       AND head.representation_version = 2
     WHERE token.token_id = inserted.token_id
       AND inserted.representation_version = 2;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_token_numeric_dependency_head_setwise
    ON execution.semantic_parser_token;
CREATE TRIGGER semantic_parser_token_numeric_dependency_head_setwise
AFTER INSERT ON execution.semantic_parser_token
REFERENCING NEW TABLE AS inserted_token
FOR EACH STATEMENT
EXECUTE FUNCTION execution.resolve_numeric_parser_dependency_heads();

COMMIT;
