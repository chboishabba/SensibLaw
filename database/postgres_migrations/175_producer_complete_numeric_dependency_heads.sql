BEGIN;

-- 175: the strict numeric parser already owns one complete bounded partition
-- token fibre before authority insertion.  Migration 150 resolved dependency
-- heads after INSERT by joining the transition table back to the persistent
-- token table and UPDATEing every freshly inserted tuple.  Live prefix profiling
-- showed that physical repair dominates the early numeric runtime and doubles
-- token-table mutations even though the head relation was known at producer time.
--
-- A producer that supplies final token_id, sentence_id and head_token_id on the
-- first INSERT may advertise this transaction-local capability.  The generic
-- statement trigger remains fail-closed for every other writer.

CREATE OR REPLACE FUNCTION execution.resolve_numeric_parser_dependency_heads()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_setting(
        'sensiblaw.producer_complete_numeric_heads',
        TRUE
    ) = 'on' THEN
        -- The producer-complete path already inserted the exact numeric edge.
        -- Generic head integrity remains independently fenced by migration 152.
        RETURN NULL;
    END IF;

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

CREATE OR REPLACE FUNCTION execution.numeric_parser_producer_complete_heads_ready()
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
SELECT TRUE;
$$;

COMMIT;
