BEGIN;

-- 134: reject entity spans that end at a structurally incomplete boundary.
--
-- Raw parser spans remain immutable evidence.  A provider label must not end
-- on a determiner, pronoun, adposition, conjunction, particle, or punctuation
-- token: those endings are evidence that the statistical span is truncated or
-- includes surrounding prose rather than naming a complete entity.

CREATE TABLE IF NOT EXISTS execution.semantic_parser_entity_quality_terminal_pos (
    pos_symbol_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO execution.semantic_parser_entity_quality_terminal_pos(pos_symbol_id)
SELECT symbol.symbol_id
  FROM execution.semantic_symbol AS symbol
 WHERE symbol.kind_id=3
   AND symbol.symbol_text IN ('DET','PRON','ADP','CCONJ','SCONJ','PART','PUNCT')
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW execution.semantic_parser_entity_span_quality_v1 AS
WITH token_geometry AS MATERIALIZED (
    SELECT entity.entity_id,entity.entity_type_symbol_id,entity.sentence_ref,
           entity.start_char,entity.end_char,
           count(token.token_id)::BIGINT AS token_count,
           min(token.start_char) AS token_start,
           max(token.end_char) AS token_end,
           min(token.local_token_ordinal) AS first_ordinal,
           max(token.local_token_ordinal) AS last_ordinal,
           count(*) FILTER (
               WHERE EXISTS (
                   SELECT 1
                     FROM execution.semantic_parser_entity_quality_pos AS q
                    WHERE q.quality_role=1
                      AND q.pos_symbol_id=token.pos_symbol_id
               )
           )::BIGINT AS verbal_token_count,
           count(*) FILTER (
               WHERE EXISTS (
                   SELECT 1
                     FROM execution.semantic_parser_entity_quality_pos AS q
                    WHERE q.quality_role=2
                      AND q.pos_symbol_id=token.pos_symbol_id
               )
           )::BIGINT AS nominal_token_count
      FROM execution.semantic_parser_entity_span AS entity
      LEFT JOIN execution.semantic_parser_token AS token
        ON token.run_ref=entity.run_ref
       AND token.document_ref=entity.document_ref
       AND token.sentence_ref=entity.sentence_ref
       AND token.representation_version=2
       AND token.start_char>=entity.start_char
       AND token.end_char<=entity.end_char
     WHERE entity.representation_version=2
     GROUP BY entity.entity_id,entity.entity_type_symbol_id,entity.sentence_ref,
              entity.start_char,entity.end_char
), classified AS (
    SELECT geometry.*,
           EXISTS (
               SELECT 1
                 FROM execution.semantic_parser_provider_entity_type AS allowed
                WHERE allowed.entity_type_symbol_id=geometry.entity_type_symbol_id
                  AND allowed.provider_world_bearing
           ) AS provider_world_bearing,
           CASE
             WHEN geometry.sentence_ref IS NULL THEN 10
             WHEN geometry.token_count=0 THEN 11
             WHEN geometry.token_start<>geometry.start_char
               OR geometry.token_end<>geometry.end_char THEN 12
             WHEN geometry.first_ordinal IS NULL OR geometry.last_ordinal IS NULL
               OR geometry.token_count<>(geometry.last_ordinal-geometry.first_ordinal+1)
               THEN 13
             WHEN geometry.verbal_token_count>0 THEN 14
             WHEN geometry.token_count>16
               OR geometry.end_char-geometry.start_char>256 THEN 15
             WHEN NOT EXISTS (
                 SELECT 1
                   FROM execution.semantic_parser_provider_entity_type AS allowed
                  WHERE allowed.entity_type_symbol_id=geometry.entity_type_symbol_id
                    AND allowed.provider_world_bearing
             ) THEN 16
             WHEN geometry.nominal_token_count=0 THEN 17
             WHEN EXISTS (
                 SELECT 1
                   FROM execution.semantic_parser_token AS terminal_token
                   JOIN execution.semantic_parser_entity_quality_terminal_pos AS terminal
                     ON terminal.pos_symbol_id=terminal_token.pos_symbol_id
                  WHERE terminal_token.representation_version=2
                    AND terminal_token.sentence_ref=geometry.sentence_ref
                    AND terminal_token.local_token_ordinal=geometry.last_ordinal
             ) THEN 18
             ELSE 1
           END::SMALLINT AS quality_state
      FROM token_geometry AS geometry
)
SELECT classified.*,(classified.quality_state=1) AS provider_admissible
  FROM classified;

UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_h9_entity_bearing_v1 AS bearing
        WHERE bearing.demand_id=need.demand_id
          AND bearing.source_object_id=need.anchor_object_id
   );

SELECT execution.refresh_numeric_pnf_external_request_observer_state();
SELECT execution.refresh_numeric_pnf_external_request_cache_state();

COMMIT;
