BEGIN;

CREATE TABLE IF NOT EXISTS execution.semantic_parser_annotation_origin (
    origin_id SMALLINT PRIMARY KEY,
    origin_name TEXT NOT NULL UNIQUE
);

INSERT INTO execution.semantic_parser_annotation_origin (origin_id, origin_name)
VALUES
    (1, 'parser'),
    (2, 'orthographic_fallback'),
    (3, 'pos_fallback'),
    (4, 'unavailable')
ON CONFLICT DO NOTHING;

ALTER TABLE execution.semantic_parser_token
    ADD COLUMN IF NOT EXISTS lemma_origin_id SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_parser_annotation_origin(origin_id)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS pos_origin_id SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_parser_annotation_origin(origin_id)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS tag_origin_id SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_parser_annotation_origin(origin_id)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS dependency_origin_id SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_parser_annotation_origin(origin_id)
        ON DELETE RESTRICT;

ALTER TABLE execution.semantic_parser_token
    DROP CONSTRAINT IF EXISTS semantic_parser_token_numeric_annotation_origin_ck;
ALTER TABLE execution.semantic_parser_token
    ADD CONSTRAINT semantic_parser_token_numeric_annotation_origin_ck CHECK (
        representation_version <> 2
        OR (
            lemma_origin_id IN (1, 2)
            AND pos_origin_id = 1
            AND tag_origin_id IN (1, 3)
            AND dependency_origin_id = 1
        )
    );

-- The strict v2 path requires POS/dependency capabilities. It may explicitly
-- derive a lemma from orthography or a fine tag from coarse POS, but those
-- derivations are not represented as parser annotations.
CREATE OR REPLACE FUNCTION execution.validate_numeric_parser_annotation_origins()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.representation_version <> 2 THEN
        RETURN NEW;
    END IF;
    IF NEW.lemma_origin_id = 2
       AND NEW.lemma_symbol_id IS DISTINCT FROM NEW.orth_symbol_id THEN
        RAISE EXCEPTION
            'orthographic lemma fallback for token % does not equal orth symbol',
            NEW.token_id;
    END IF;
    IF NEW.tag_origin_id = 3
       AND NEW.tag_symbol_id IS DISTINCT FROM NEW.pos_symbol_id THEN
        RAISE EXCEPTION
            'POS tag fallback for token % does not equal POS symbol',
            NEW.token_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_token_annotation_origins
    ON execution.semantic_parser_token;
CREATE TRIGGER semantic_parser_token_annotation_origins
BEFORE INSERT OR UPDATE OF
    representation_version,
    orth_symbol_id,
    lemma_symbol_id,
    pos_symbol_id,
    tag_symbol_id,
    lemma_origin_id,
    pos_origin_id,
    tag_origin_id,
    dependency_origin_id
ON execution.semantic_parser_token
FOR EACH ROW
EXECUTE FUNCTION execution.validate_numeric_parser_annotation_origins();

COMMIT;
