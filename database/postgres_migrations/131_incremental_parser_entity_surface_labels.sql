BEGIN;

-- 131: keep the provider-facing entity surface projection current for newly
-- parsed documents. The parser writes tokens before/with entity spans; this
-- trigger refreshes the bounded entity-label projection after a numeric span is
-- inserted or retargeted. The corpus-wide refresh in migration 130 remains the
-- idempotent repair/backfill path.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_parser_entity_surface_label_on_span()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.representation_version=2 AND NEW.entity_id IS NOT NULL THEN
        WITH ordered AS MATERIALIZED (
            SELECT token.token_id,token.start_char,token.end_char,
                   symbol.symbol_text,
                   lag(token.end_char) OVER (
                       ORDER BY token.start_char,token.token_id
                   ) AS previous_end
              FROM execution.semantic_parser_token AS token
              JOIN execution.semantic_symbol AS symbol
                ON symbol.symbol_id=token.orth_symbol_id
             WHERE token.run_ref=NEW.run_ref
               AND token.document_ref=NEW.document_ref
               AND token.sentence_ref=NEW.sentence_ref
               AND token.start_char>=NEW.start_char
               AND token.end_char<=NEW.end_char
               AND token.representation_version=2
        ), surface AS (
            SELECT string_agg(
                       CASE
                         WHEN previous_end IS NULL THEN symbol_text
                         ELSE repeat(' ',greatest((start_char-previous_end)::INTEGER,0))
                              || symbol_text
                       END,
                       '' ORDER BY start_char,token_id
                   ) AS surface_text
              FROM ordered
        )
        INSERT INTO execution.semantic_pnf_parser_entity_surface_label
            (entity_id,label_symbol_id,entity_type_symbol_id,updated_at)
        SELECT NEW.entity_id,
               execution.ensure_semantic_symbol(1::SMALLINT,surface.surface_text),
               NEW.entity_type_symbol_id,CURRENT_TIMESTAMP
          FROM surface
         WHERE surface.surface_text IS NOT NULL AND surface.surface_text<>''
        ON CONFLICT(entity_id) DO UPDATE SET
            label_symbol_id=EXCLUDED.label_symbol_id,
            entity_type_symbol_id=EXCLUDED.entity_type_symbol_id,
            updated_at=CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_entity_surface_label_refresh
    ON execution.semantic_parser_entity_span;
CREATE TRIGGER semantic_parser_entity_surface_label_refresh
AFTER INSERT OR UPDATE OF run_ref,document_ref,sentence_ref,start_char,end_char,
    entity_type_symbol_id,representation_version
ON execution.semantic_parser_entity_span
FOR EACH ROW
EXECUTE FUNCTION execution.refresh_numeric_pnf_parser_entity_surface_label_on_span();

COMMIT;
