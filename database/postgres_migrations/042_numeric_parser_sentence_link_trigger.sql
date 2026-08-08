BEGIN;

CREATE OR REPLACE FUNCTION execution.assign_numeric_parser_sentence_id()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.representation_version <> 2 THEN
        RETURN NEW;
    END IF;
    IF NEW.sentence_id IS NULL THEN
        SELECT sentence_id
          INTO NEW.sentence_id
          FROM execution.semantic_parser_sentence
         WHERE sentence_ref = NEW.sentence_ref
           AND representation_version = 2;
    END IF;
    IF NEW.sentence_id IS NULL THEN
        RAISE EXCEPTION
            'numeric parser token lacks a v2 sentence identity for %',
            NEW.sentence_ref;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_token_numeric_sentence_id
    ON execution.semantic_parser_token;
CREATE TRIGGER semantic_parser_token_numeric_sentence_id
BEFORE INSERT OR UPDATE OF sentence_ref, representation_version
ON execution.semantic_parser_token
FOR EACH ROW
EXECUTE FUNCTION execution.assign_numeric_parser_sentence_id();

COMMIT;
