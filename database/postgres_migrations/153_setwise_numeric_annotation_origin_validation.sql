BEGIN;

-- 153: migration 059 validates parser fallback origins correctly but invokes a
-- BEFORE ROW PL/pgSQL function for every numeric token and performs point symbol
-- lookups for each fallback token. Strict parser persistence already inserts one
-- bounded token fibre with numeric symbol ids. Validate only the fallback rows
-- as one transition-table relation and retain the row trigger for generic writers.

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
WHEN (
    current_setting(
        'sensiblaw.setwise_numeric_annotation_origins',
        TRUE
    ) IS DISTINCT FROM 'on'
)
EXECUTE FUNCTION execution.validate_numeric_parser_annotation_origins();

CREATE OR REPLACE FUNCTION execution.validate_numeric_parser_annotation_origin_fibre()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Generic writers did not opt into this statement-level authority and are
    -- already checked by the original migration-059 row trigger.
    IF current_setting(
        'sensiblaw.setwise_numeric_annotation_origins',
        TRUE
    ) IS DISTINCT FROM 'on' THEN
        RETURN NULL;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM inserted_token AS token
          LEFT JOIN execution.semantic_symbol AS orth
            ON orth.symbol_id = token.orth_symbol_id
           AND orth.kind_id = 1
          LEFT JOIN execution.semantic_symbol AS lemma
            ON lemma.symbol_id = token.lemma_symbol_id
           AND lemma.kind_id = 2
         WHERE token.representation_version = 2
           AND token.lemma_origin_id = 2
           AND (
               orth.symbol_id IS NULL
               OR lemma.symbol_id IS NULL
               OR lemma.symbol_text IS DISTINCT FROM orth.symbol_text
           )
    ) THEN
        RAISE EXCEPTION
            'numeric parser orthographic lemma fallback does not match orth text';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM inserted_token AS token
          LEFT JOIN execution.semantic_symbol AS pos
            ON pos.symbol_id = token.pos_symbol_id
           AND pos.kind_id = 3
          LEFT JOIN execution.semantic_symbol AS tag
            ON tag.symbol_id = token.tag_symbol_id
           AND tag.kind_id = 4
         WHERE token.representation_version = 2
           AND token.tag_origin_id = 3
           AND (
               pos.symbol_id IS NULL
               OR tag.symbol_id IS NULL
               OR tag.symbol_text IS DISTINCT FROM pos.symbol_text
           )
    ) THEN
        RAISE EXCEPTION
            'numeric parser POS tag fallback does not match POS text';
    END IF;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_token_annotation_origins_setwise
    ON execution.semantic_parser_token;
CREATE TRIGGER semantic_parser_token_annotation_origins_setwise
AFTER INSERT ON execution.semantic_parser_token
REFERENCING NEW TABLE AS inserted_token
FOR EACH STATEMENT
EXECUTE FUNCTION execution.validate_numeric_parser_annotation_origin_fibre();

CREATE OR REPLACE FUNCTION execution.numeric_parser_setwise_annotation_origin_ready()
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
SELECT TRUE;
$$;

COMMIT;
