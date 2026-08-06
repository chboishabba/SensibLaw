BEGIN;

-- Numeric dependency edges are parser observations, not recoverable defaults.
-- A v2 token must finish its transaction with one committed head in the same
-- sentence.  A self-loop is valid only when the parser-declared head span is
-- exactly the token's own span; every non-self edge must agree with the
-- referenced head token's committed coordinates.
CREATE OR REPLACE FUNCTION execution.validate_numeric_parser_head_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    token_row RECORD;
    head_row RECORD;
BEGIN
    -- Constraint triggers are deferred. Re-read the current row so the INSERT
    -- event observes the head assigned later in the same fenced transaction.
    SELECT token_id,
           sentence_id,
           start_char,
           end_char,
           head_token_id,
           head_start_char,
           head_end_char,
           representation_version
      INTO token_row
      FROM execution.semantic_parser_token
     WHERE token_id = NEW.token_id;

    -- A row deleted or converted away from numeric authority before commit no
    -- longer carries a v2 dependency obligation.
    IF token_row.token_id IS NULL
       OR token_row.representation_version <> 2 THEN
        RETURN NULL;
    END IF;

    IF token_row.head_token_id IS NULL THEN
        RAISE EXCEPTION
            'numeric parser token % has no committed dependency head',
            token_row.token_id;
    END IF;
    IF token_row.head_start_char IS NULL
       OR token_row.head_end_char IS NULL THEN
        RAISE EXCEPTION
            'numeric parser token % has no declared head coordinates',
            token_row.token_id;
    END IF;

    SELECT token_id, sentence_id, start_char, end_char, representation_version
      INTO head_row
      FROM execution.semantic_parser_token
     WHERE token_id = token_row.head_token_id;

    IF head_row.token_id IS NULL
       OR head_row.representation_version <> 2 THEN
        RAISE EXCEPTION
            'numeric parser token % references absent/non-numeric head %',
            token_row.token_id,
            token_row.head_token_id;
    END IF;
    IF head_row.sentence_id IS DISTINCT FROM token_row.sentence_id THEN
        RAISE EXCEPTION
            'numeric parser token % crosses sentence identity to head %',
            token_row.token_id,
            token_row.head_token_id;
    END IF;

    IF token_row.head_token_id = token_row.token_id THEN
        IF token_row.head_start_char IS DISTINCT FROM token_row.start_char
           OR token_row.head_end_char IS DISTINCT FROM token_row.end_char THEN
            RAISE EXCEPTION
                'numeric parser self-head % lacks explicit self coordinates',
                token_row.token_id;
        END IF;
    ELSE
        IF token_row.head_start_char IS DISTINCT FROM head_row.start_char
           OR token_row.head_end_char IS DISTINCT FROM head_row.end_char THEN
            RAISE EXCEPTION
                'numeric parser token % head coordinates do not identify head %',
                token_row.token_id,
                token_row.head_token_id;
        END IF;
    END IF;

    RETURN NULL;
END;
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
EXECUTE FUNCTION execution.validate_numeric_parser_head_integrity();

COMMIT;
