BEGIN;

-- 158: migration 131 kept parser-entity surface labels current with a FOR EACH
-- ROW trigger. Each span independently rescanned its covered parser tokens,
-- rebuilt spacing, and called ensure_semantic_symbol. The semantic projection is
-- span-local and therefore factorizes over the inserted/updated entity fibre.
--
-- Surface text is an allowed boundary value here: this relation exists exactly
-- to preserve the parser's human-readable entity label for provider lookup and
-- audit. Downstream identity/H9 authority remains numeric and occurrence-based.

DROP TRIGGER IF EXISTS semantic_parser_entity_surface_label_refresh
    ON execution.semantic_parser_entity_span;

CREATE OR REPLACE FUNCTION execution.project_parser_entity_surface_labels_inserted()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH entity AS MATERIALIZED (
        SELECT entity_id,run_ref,document_ref,sentence_ref,start_char,end_char,
               entity_type_symbol_id
          FROM inserted_entity
         WHERE representation_version=2
           AND entity_id IS NOT NULL
           AND entity_type_symbol_id IS NOT NULL
    ), token_row AS MATERIALIZED (
        SELECT entity.entity_id,entity.entity_type_symbol_id,
               token.token_id,token.start_char,token.end_char,
               symbol.symbol_text,
               lag(token.end_char) OVER (
                   PARTITION BY entity.entity_id
                   ORDER BY token.start_char,token.token_id
               ) AS previous_end
          FROM entity
          JOIN execution.semantic_parser_token AS token
            ON token.run_ref=entity.run_ref
           AND token.document_ref=entity.document_ref
           AND token.sentence_ref=entity.sentence_ref
           AND token.start_char>=entity.start_char
           AND token.end_char<=entity.end_char
           AND token.representation_version=2
          JOIN execution.semantic_symbol AS symbol
            ON symbol.symbol_id=token.orth_symbol_id
    ), surface AS MATERIALIZED (
        SELECT token_row.entity_id,
               min(token_row.entity_type_symbol_id) AS entity_type_symbol_id,
               string_agg(
                   CASE
                     WHEN token_row.previous_end IS NULL THEN token_row.symbol_text
                     ELSE repeat(
                         ' ',
                         greatest(
                             (token_row.start_char-token_row.previous_end)::INTEGER,
                             0
                         )
                     ) || token_row.symbol_text
                   END,
                   '' ORDER BY token_row.start_char,token_row.token_id
               ) AS surface_text
          FROM token_row
         GROUP BY token_row.entity_id
    ), valid_surface AS MATERIALIZED (
        SELECT * FROM surface
         WHERE surface_text IS NOT NULL AND surface_text<>''
    ), intern AS (
        INSERT INTO execution.semantic_symbol(kind_id,symbol_text,symbol_digest)
        SELECT DISTINCT 1::SMALLINT,
               valid_surface.surface_text,
               execution.semantic_symbol_digest_value(
                   1::SMALLINT,
                   valid_surface.surface_text
               )
          FROM valid_surface
        ON CONFLICT(kind_id,symbol_text) DO NOTHING
        RETURNING symbol_id
    )
    INSERT INTO execution.semantic_pnf_parser_entity_surface_label
        (entity_id,label_symbol_id,entity_type_symbol_id,updated_at)
    SELECT valid_surface.entity_id,
           symbol.symbol_id,
           valid_surface.entity_type_symbol_id,
           CURRENT_TIMESTAMP
      FROM valid_surface
      JOIN execution.semantic_symbol AS symbol
        ON symbol.kind_id=1
       AND symbol.symbol_text=valid_surface.surface_text
    ON CONFLICT(entity_id) DO UPDATE SET
        label_symbol_id=EXCLUDED.label_symbol_id,
        entity_type_symbol_id=EXCLUDED.entity_type_symbol_id,
        updated_at=CURRENT_TIMESTAMP;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_entity_surface_label_refresh_insert
    ON execution.semantic_parser_entity_span;
CREATE TRIGGER semantic_parser_entity_surface_label_refresh_insert
AFTER INSERT ON execution.semantic_parser_entity_span
REFERENCING NEW TABLE AS inserted_entity
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_parser_entity_surface_labels_inserted();

CREATE OR REPLACE FUNCTION execution.project_parser_entity_surface_labels_updated()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS MATERIALIZED (
        SELECT current.*
          FROM updated_entity AS current
          JOIN prior_entity AS prior USING(entity_id)
         WHERE current.representation_version=2
           AND current.entity_id IS NOT NULL
           AND current.entity_type_symbol_id IS NOT NULL
           AND (
               current.run_ref IS DISTINCT FROM prior.run_ref
               OR current.document_ref IS DISTINCT FROM prior.document_ref
               OR current.sentence_ref IS DISTINCT FROM prior.sentence_ref
               OR current.start_char IS DISTINCT FROM prior.start_char
               OR current.end_char IS DISTINCT FROM prior.end_char
               OR current.entity_type_symbol_id IS DISTINCT FROM prior.entity_type_symbol_id
               OR current.representation_version IS DISTINCT FROM prior.representation_version
           )
    ), token_row AS MATERIALIZED (
        SELECT changed.entity_id,changed.entity_type_symbol_id,
               token.token_id,token.start_char,token.end_char,
               symbol.symbol_text,
               lag(token.end_char) OVER (
                   PARTITION BY changed.entity_id
                   ORDER BY token.start_char,token.token_id
               ) AS previous_end
          FROM changed
          JOIN execution.semantic_parser_token AS token
            ON token.run_ref=changed.run_ref
           AND token.document_ref=changed.document_ref
           AND token.sentence_ref=changed.sentence_ref
           AND token.start_char>=changed.start_char
           AND token.end_char<=changed.end_char
           AND token.representation_version=2
          JOIN execution.semantic_symbol AS symbol
            ON symbol.symbol_id=token.orth_symbol_id
    ), surface AS MATERIALIZED (
        SELECT token_row.entity_id,
               min(token_row.entity_type_symbol_id) AS entity_type_symbol_id,
               string_agg(
                   CASE
                     WHEN token_row.previous_end IS NULL THEN token_row.symbol_text
                     ELSE repeat(
                         ' ',
                         greatest(
                             (token_row.start_char-token_row.previous_end)::INTEGER,
                             0
                         )
                     ) || token_row.symbol_text
                   END,
                   '' ORDER BY token_row.start_char,token_row.token_id
               ) AS surface_text
          FROM token_row
         GROUP BY token_row.entity_id
    ), valid_surface AS MATERIALIZED (
        SELECT * FROM surface
         WHERE surface_text IS NOT NULL AND surface_text<>''
    ), intern AS (
        INSERT INTO execution.semantic_symbol(kind_id,symbol_text,symbol_digest)
        SELECT DISTINCT 1::SMALLINT,
               valid_surface.surface_text,
               execution.semantic_symbol_digest_value(
                   1::SMALLINT,
                   valid_surface.surface_text
               )
          FROM valid_surface
        ON CONFLICT(kind_id,symbol_text) DO NOTHING
        RETURNING symbol_id
    )
    INSERT INTO execution.semantic_pnf_parser_entity_surface_label
        (entity_id,label_symbol_id,entity_type_symbol_id,updated_at)
    SELECT valid_surface.entity_id,
           symbol.symbol_id,
           valid_surface.entity_type_symbol_id,
           CURRENT_TIMESTAMP
      FROM valid_surface
      JOIN execution.semantic_symbol AS symbol
        ON symbol.kind_id=1
       AND symbol.symbol_text=valid_surface.surface_text
    ON CONFLICT(entity_id) DO UPDATE SET
        label_symbol_id=EXCLUDED.label_symbol_id,
        entity_type_symbol_id=EXCLUDED.entity_type_symbol_id,
        updated_at=CURRENT_TIMESTAMP;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_entity_surface_label_refresh_update
    ON execution.semantic_parser_entity_span;
CREATE TRIGGER semantic_parser_entity_surface_label_refresh_update
AFTER UPDATE ON execution.semantic_parser_entity_span
REFERENCING OLD TABLE AS prior_entity NEW TABLE AS updated_entity
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_parser_entity_surface_labels_updated();

COMMIT;
